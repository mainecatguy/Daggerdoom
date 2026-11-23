<#
Overnight loop: one Claude session works on work/goal.md on its own branch.
When it reports DONE, real builds and a fresh read-only verifier check it.
Passing work advances local integration. Nothing ever touches main.
Stops on: verified, blocked, budget, time, or round limit.

Run:        .\scripts\overnight\run.ps1
Hard goal:  .\scripts\overnight\run.ps1 -Model opus
From chat:  .\scripts\overnight\run.ps1 -ContinueSession <session-id>
Push too:   .\scripts\overnight\run.ps1 -Push
#>
param(
    [string]$GoalFile,
    [guid]$ContinueSession,
    [string]$Model = 'sonnet',
    [double]$Hours = 8,
    [int]$MaxRounds = 12,
    [int]$MaxTurnsPerRound = 150,
    [double]$MaxUsd = 20,
    [double]$VerifierMaxUsd = 2,
    [int]$RetryMinutes = 15,
    [int]$MaxFailures = 12,
    [string]$RunDir,
    [string]$CheckScript = (Join-Path $PSScriptRoot 'check.ps1'),
    [string]$ClaudeExe = 'claude',
    [string]$ClaudePrefix = '',
    [string]$Target = 'integration',
    [string]$Lane = '',
    [switch]$Push
)

# --- Constants ---
$Integration = "refs/heads/$Target"
# Blocked up front by agent-settings.json. Rechecked here because shell subprocesses can bypass deny rules.
$Protected = 'AGENTS.md', 'CLAUDE.md', '.claude/', '.github/', 'scripts/overnight/', '.gitignore', 'GameResources/'
$AgentSchema = '{"type":"object","properties":{"status":{"type":"string","enum":["CONTINUE","DONE","BLOCKED"]},"summary":{"type":"string"},"questions":{"type":"array","items":{"type":"string"}},"oversights":{"type":"array","items":{"type":"string"}}},"required":["status","summary"]}'
$VerifierSchema = '{"type":"object","properties":{"verdict":{"type":"string","enum":["PASS","FAIL"]},"problems":{"type":"string"}},"required":["verdict","problems"]}'
$MaxDiffChars = 60000
$UnityArtifacts = @('daggerfall-unity-master/Assets/AddressableAssetsData/Windows/addressables_content_state.bin')

# --- Helpers ---
function RepoGit {
    $Dir = [string]$args[0]
    [string[]]$GitArgs = @($args | Select-Object -Skip 1)
    $previous = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $output = & git -C $Dir -c core.quotepath=off @GitArgs 2>$null
    $code = $LASTEXITCODE; $ErrorActionPreference = $previous
    if ($code -ne 0) { throw "git $($GitArgs -join ' ') failed ($code)" }
    $output
}

function Write-Text([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

function Invoke-Logged([string]$Exe, [string]$ArgLine, [string]$InputText, [string]$Log) {
    $in = "$Log.in"; Write-Text $in $InputText
    $p = Start-Process -FilePath $Exe -ArgumentList $ArgLine -WorkingDirectory $Worktree -NoNewWindow -PassThru `
        -RedirectStandardInput $in -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
    $null = $p.Handle
    $ms = [Math]::Max(60000, [int][Math]::Min(2147483000, ($Deadline - (Get-Date)).TotalMilliseconds))
    if (-not $p.WaitForExit($ms)) { & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null; return -1 }
    $p.WaitForExit(); $p.ExitCode
}

function Read-Result([string]$Log) {
    try { Get-Content $Log -Raw -ErrorAction Stop | ConvertFrom-Json } catch { $null }
}

function Get-SchemaArg([string]$Schema) { "--json-schema `"$($Schema.Replace('"', '\"'))`"" }

function Get-Spent { $script:PriorSessionUsd + $script:SessionUsd + $script:VerifierUsd }

function Save-Work {
    # Every Unity build rewrites these files, so they must never ride along in an automatic commit.
    foreach ($artifact in $UnityArtifacts) {
        if (RepoGit $Worktree status --porcelain -- $artifact) {
            RepoGit $Worktree restore --source=HEAD --staged --worktree -- $artifact | Out-Null
        }
    }
    if (RepoGit $Worktree status --porcelain) {
        RepoGit $Worktree add -A | Out-Null
        RepoGit $Worktree commit -q -m "overnight: save work in progress" | Out-Null
    }
}

# Collects raw agent reports in the main checkout for the orchestrator to triage, without duplicates.
function Add-AgentReports($Items, $Kind) {
    $new = @($Items | ForEach-Object { ([string]$_ -replace '\s+', ' ').Trim() } | Where-Object { $_ })
    if (-not $new.Count) { return }
    $lines = if (Test-Path $ReportsFile) { @([IO.File]::ReadAllLines($ReportsFile)) } else { @('# Agent reports awaiting orchestrator triage', '') }
    foreach ($q in $new) {
        if (-not @($lines | Where-Object { $_.EndsWith("] [$Kind] $q") }).Count) { $lines += "- [$Stamp] [$Kind] $q" }
    }
    New-Item -ItemType Directory -Force (Split-Path $ReportsFile -Parent) | Out-Null
    Write-Text $ReportsFile (($lines -join "`n") + "`n")
}

# --- Verification: protected paths, real build, independent verifier ---
# Returns $null when verified, otherwise feedback for the agent.
function Test-Work([string]$Tag) {
    $changed = @(RepoGit $Worktree diff --name-only --no-renames $Base HEAD)
    if ($changed.Count -eq 0) { return 'You reported DONE, but the branch has no changes.' }
    $bad = @($changed | Where-Object { $f = $_; $Protected | Where-Object { $f -eq $_ -or ($_.EndsWith('/') -and $f.StartsWith($_, 'OrdinalIgnoreCase')) } })
    if ($bad.Count) { return "Undo your changes to these protected paths: $($bad -join ', ')" }

    $checkCode = Invoke-Logged 'powershell.exe' "-NoProfile -ExecutionPolicy Bypass -File `"$CheckScript`" -Worktree `"$Worktree`" -Base $Base" '' "$Tag-check.log"
    $checkTail = (Get-Content "$Tag-check.log", "$Tag-check.log.err" -Tail 30 -ErrorAction SilentlyContinue) -join "`n"
    if ($checkCode -ne 0) { $script:CheckFails++; return "The build and startup check failed with exit code $checkCode.`n$checkTail" }
    Save-Work

    # Give the verifier the diff, but not the author's reasoning.
    $head = RepoGit $Worktree rev-parse HEAD
    $diff = (RepoGit $Worktree diff --no-color $Base HEAD) -join "`n"
    if ($diff.Length -gt $MaxDiffChars) { $diff = $diff.Substring(0, $MaxDiffChars) + "`n[Diff truncated. Read the changed files for the rest.]" }
    $stat = (RepoGit $Worktree diff --stat $Base HEAD) -join "`n"
    $prompt = $VerifierPrompt.Replace('{{GOAL}}', $Goal).Replace('{{COMMITS}}', ((RepoGit $Worktree log --oneline "${Base}..HEAD") -join "`n")).Replace('{{STAT}}', $stat).Replace('{{DIFF}}', $diff).Replace('{{CHECK}}', $checkTail)
    $budget = [Math]::Min($VerifierMaxUsd, $MaxUsd - (Get-Spent)).ToString('0.####', [Globalization.CultureInfo]::InvariantCulture)
    $line = ("$ClaudePrefix -p --no-session-persistence --setting-sources project --strict-mcp-config --model sonnet --tools Read,Grep,Glob --permission-mode dontAsk --allowedTools Read,Grep,Glob --max-turns 40 --max-budget-usd $budget --output-format json $(Get-SchemaArg $VerifierSchema)").Trim()
    $code = Invoke-Logged $ClaudeExe $line $prompt "$Tag-verifier.log"
    $result = Read-Result "$Tag-verifier.log"
    if ($result) { $script:VerifierUsd += [double]$result.total_cost_usd }
    if ((RepoGit $Worktree rev-parse HEAD) -ne $head -or (RepoGit $Worktree status --porcelain)) { throw 'The verifier changed the worktree.' }
    if ($code -ne 0 -or -not $result.structured_output) { return 'The verifier could not finish. Confirm your work is still complete, then report DONE again.' }
    if ($result.structured_output.verdict -eq 'PASS') { return $null }
    $script:VerifierFails++
    "An independent verifier rejected this work:`n$($result.structured_output.problems)"
}

# --- Setup: paths, tools, branch, and persistent worktree ---
$Repo = RepoGit $PSScriptRoot rev-parse --show-toplevel
if (-not $GoalFile) { $GoalFile = Join-Path $Repo 'work\goal.md' }
if (-not (Test-Path $GoalFile)) { throw "Write the goal in $GoalFile first." }
if (-not $RunDir) { $RunDir = Join-Path (Split-Path $Repo -Parent) ((Split-Path $Repo -Leaf) + '-loop') }
$Worktree = Join-Path $RunDir 'worktree'
$Stamp = Get-Date -Format yyyyMMdd-HHmmss
$Branch = if ($Lane) { "agent/$Lane-$Stamp" } else { "agent/$Stamp" }
$Logs = Join-Path $RunDir "logs\$Stamp"
$Settings = Join-Path $PSScriptRoot 'agent-settings.json'
# Agents leave their one-click demos here, outside the repo, because demos contain files derived from game data.
$ReviewDir = Join-Path (Split-Path $Repo -Parent) ((Split-Path $Repo -Leaf) + '-loop\review')
New-Item -ItemType Directory -Force $ReviewDir | Out-Null
$StartedAt = Get-Date
$Deadline = $StartedAt.AddHours($Hours)

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath = if (Test-Path $vswhere) { & $vswhere -latest -property installationPath }
$toolDirs = @("$vsPath\MSBuild\Current\Bin", "$vsPath\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin", "$env:ProgramFiles\Unity\Hub\Editor\2019.4.41f2\Editor", "$env:LOCALAPPDATA\Programs\Python\Python313", "$RunDir\DoomDaggerfall-build\uzdoom\Release") | Where-Object { Test-Path $_ }
$env:Path = (@($toolDirs) + $env:Path) -join ';'
$env:GIT_TERMINAL_PROMPT = '0'; $env:GCM_INTERACTIVE = 'never'

$Base = RepoGit $Repo rev-parse --verify $Integration
if (@(RepoGit $Repo worktree list --porcelain | Where-Object { $_ -eq "branch $Integration" }).Count) { throw 'Switch away from integration before running.' }
New-Item -ItemType Directory -Force $Logs | Out-Null
RepoGit $Repo worktree prune | Out-Null
# Kept between runs so Unity and CMake can reuse their caches.
if (-not (Test-Path $Worktree)) { RepoGit $Repo worktree add -q --detach $Worktree $Base | Out-Null }
if (RepoGit $Worktree status --porcelain) { throw "$Worktree has uncommitted changes. Review them first." }
RepoGit $Worktree switch -q -c $Branch $Base | Out-Null

$Goal = [IO.File]::ReadAllText($GoalFile)
$QuestionsFile = Join-Path $Repo 'work\questions.md'
$ReportsFile = Join-Path $Repo 'work\agent-reports.md'
$OpenQuestions = (@($QuestionsFile, $ReportsFile) | Where-Object { Test-Path $_ } | ForEach-Object { [IO.File]::ReadAllText($_) }) -join "`n"
if (-not $OpenQuestions) { $OpenQuestions = 'None.' }
$VerifierPrompt = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'verifier.md'))
$FirstPrompt = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'agent.md')).Replace('{{GOAL}}', $Goal).Replace('{{NOTES}}', "work/notes/$Stamp.md").Replace('{{QUESTIONS}}', $OpenQuestions)
if ($ContinueSession) {
    $FirstPrompt = "You are continuing from the planning conversation above, now as an unattended run in a separate checkout on branch $Branch. Use the decisions from that conversation, and use paths relative to the current directory.`n`n$FirstPrompt"
}
$ContinuePrompt = 'Continue working toward the goal. Check your notes and git log if you need to reorient.'

# --- Main loop: run the same session until a stop condition ---
$session = [guid]::NewGuid().ToString(); $started = $false
$next = $FirstPrompt; $round = 0; $failures = 0
$PriorSessionUsd = 0.0; $SessionUsd = 0.0; $VerifierUsd = 0.0
$Turns = 0; $Denials = 0; $CheckFails = 0; $VerifierFails = 0; $Verifications = 0
$result = 'limit'; $outcome = 'Stopped at the time or round limit.'; $exitCode = 1

try {
    while ($round -lt $MaxRounds -and (Get-Date) -lt $Deadline) {
        $remaining = $MaxUsd - (Get-Spent)
        if ($remaining -le 0) { $result = 'budget'; $outcome = "Stopped at the `$$MaxUsd budget."; break }
        $round++
        $tag = Join-Path $Logs "round-$round"
        # Forking leaves the owner's planning chat untouched.
        $resume = if ($started) { "--resume $session" } elseif ($ContinueSession) { "--resume $ContinueSession --fork-session" } else { "--session-id $session" }
        $budget = $remaining.ToString('0.####', [Globalization.CultureInfo]::InvariantCulture)
        Write-Output "[round $round] $Model, `$$budget left"
        $line = ("$ClaudePrefix -p --setting-sources project --strict-mcp-config --model $Model --permission-mode acceptEdits --settings `"$Settings`" --add-dir `"$ReviewDir`" $resume --max-turns $MaxTurnsPerRound --max-budget-usd $budget --output-format json $(Get-SchemaArg $AgentSchema)").Trim()
        $code = Invoke-Logged $ClaudeExe $line $next "$tag.log"
        Save-Work

        # total_cost_usd is cumulative across resumes of one session.
        $r = Read-Result "$tag.log"
        if ($r) {
            if ($r.session_id) { $session = $r.session_id }
            $SessionUsd = [double]$r.total_cost_usd
            $Turns += [int]$r.num_turns
            $Denials += @($r.permission_denials).Count
            Add-AgentReports $r.structured_output.questions 'question'
            Add-AgentReports $r.structured_output.oversights 'oversight'
        }

        # Limits exit nonzero too, so handle them before treating this as an outage.
        if ($r.subtype -eq 'error_max_budget_usd') { $result = 'budget'; $outcome = "Stopped at the `$$MaxUsd budget."; break }
        if ($r.subtype -eq 'error_max_turns') { $started = $true; $failures = 0; $next = $ContinuePrompt; continue }

        if ($code -ne 0) {
            # Usually a usage limit or outage. Wait it out without counting a round.
            $round--; $failures++
            if ($failures -ge $MaxFailures) { $result = 'error'; $outcome = "Stopped after $failures failed Claude runs. Last exit code: $code."; break }
            if (-not $started) { $PriorSessionUsd += $SessionUsd; $SessionUsd = 0.0; $session = [guid]::NewGuid().ToString(); $next = $FirstPrompt }
            Write-Output "Claude exited with $code. Waiting $RetryMinutes minutes."
            $wait = [Math]::Min($RetryMinutes * 60, [Math]::Max(0, ($Deadline - (Get-Date)).TotalSeconds))
            Start-Sleep -Seconds ([int]$wait)
            continue
        }
        $started = $true; $failures = 0

        $status = $r.structured_output.status
        if ($status -eq 'BLOCKED') { $result = 'blocked'; $outcome = "The agent needs you: $($r.structured_output.summary)"; break }
        if ($status -ne 'DONE') { $next = $ContinuePrompt; continue }

        Write-Output "[round $round] verifying"
        $Verifications++
        $feedback = Test-Work $tag
        if ($null -eq $feedback) {
            RepoGit $Repo update-ref $Integration (RepoGit $Worktree rev-parse HEAD) $Base | Out-Null
            if ($Push) { RepoGit $Repo push origin "${Integration}:${Integration}" | Out-Null }
            $result = 'verified'; $outcome = 'Verified and added to integration.'; $exitCode = 0
            break
        }
        $next = "$feedback`n`nFix this, then report your status."
    }
}
catch { $result = 'error'; $outcome = "Stopped: $($_.Exception.Message)" }
finally { try { Save-Work } catch { Write-Warning 'Could not save final work.' } }

# --- Morning report and run metrics ---
$commits = @(RepoGit $Worktree log --oneline "${Base}..$Branch")
$cost = [Math]::Round((Get-Spent), 4)
$minutes = [Math]::Round(((Get-Date) - $StartedAt).TotalMinutes, 1)
$harness = try { RepoGit $Repo rev-parse --short HEAD:scripts/overnight } catch { 'uncommitted' }
$metric = [pscustomobject]@{
    Run = $Stamp; Harness = $harness; Model = $Model; Result = $result; Rounds = $round; Turns = $Turns
    CostUsd = $cost; Minutes = $minutes; Commits = $commits.Count; Verifications = $Verifications
    CheckFails = $CheckFails; VerifierFails = $VerifierFails; Denials = $Denials
}
# The shared file can be locked, for example while it is open in a spreadsheet. Never lose the row.
$metricSaved = $false
foreach ($try in 1..12) {
    try {
        $metric | Export-Csv -LiteralPath (Join-Path $RunDir 'metrics.csv') -Append -NoTypeInformation -Encoding utf8 -ErrorAction Stop
        $metricSaved = $true; break
    }
    catch { Start-Sleep -Seconds 5 }
}
if (-not $metricSaved) {
    $metric | Export-Csv -LiteralPath (Join-Path $RunDir "metrics-$Stamp.csv") -NoTypeInformation -Encoding utf8
    Write-Warning "metrics.csv was locked. Saved this run to metrics-$Stamp.csv."
}

$report = Join-Path $RunDir 'report.md'
$openCount = if (Test-Path $ReportsFile) { @(Get-Content $ReportsFile | Where-Object { $_ -like '- *' }).Count } else { 0 }
$entry = @("## Run $Stamp", "- Result: $outcome", "- Branch: $Branch ($($commits.Count) commits)", "- Rounds: $round, turns: $Turns, estimated cost: `$$cost, minutes: $minutes", "- Agent reports awaiting triage: $openCount (work/agent-reports.md)", "- Notes: work/notes/$Stamp.md", "- Logs: $Logs", '')
Add-Content -LiteralPath $report -Value $entry -Encoding utf8
$entry | Write-Output
exit $exitCode
