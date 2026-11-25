<#
Overnight loop: one Claude session works on work/goal.md on its own branch.
When it reports DONE, real builds and a fresh read-only verifier check it. After a pass, the verifier's session is
resumed as a reviewer whose architecture and performance flags go to the owner without failing the work.
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
# The reviewer resumes the verifier's session with the same schema, so the cached prefix still matches.
$VerifierSchema = '{"type":"object","properties":{"verdict":{"type":"string","enum":["PASS","FAIL"]},"problems":{"type":"string"},"owner_flags":{"type":"array","items":{"type":"string"}}},"required":["verdict","problems"]}'
$ReviewerMaxUsd = 0.5
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
        # Line-ending-only changes can disappear when staged, and an empty commit would stop the run.
        if (RepoGit $Worktree diff --cached --name-only) {
            RepoGit $Worktree commit -q -m "overnight: save work in progress" | Out-Null
        }
    }
}

# Collects raw agent reports in the main checkout for the orchestrator to triage, without duplicates.
function Add-AgentReports($Items, $Kind) {
    $new = @($Items | ForEach-Object { ([string]$_ -replace '\s+', ' ').Trim() } | Where-Object { $_ })
    if (-not $new.Count) { return }
    $lines = if (Test-Path $ReportsFile) { @([IO.File]::ReadAllLines($ReportsFile)) } else { @("# Agent reports from run $Stamp ($(Split-Path $GoalFile -Leaf))", '') }
    foreach ($q in $new) {
        if (-not @($lines | Where-Object { $_.EndsWith("] [$Kind] $q") }).Count) { $lines += "- [$Stamp] [$Kind] $q" }
    }
    New-Item -ItemType Directory -Force (Split-Path $ReportsFile -Parent) | Out-Null
    Write-Text $ReportsFile (($lines -join "`n") + "`n")
}

# Stats cover the worker agent and its subagents, not the verifier or reviewer. A failed read leaves blanks.
function Get-RunStats {
    $blank = @{ PeakContext = ''; CacheReadTokens = ''; OutputTokens = ''; Messages = ''; ToolOutputChars = '' }
    try {
        $since = $StartedAt.ToUniversalTime().ToString('o')
        $text = & python -I (Join-Path $PSScriptRoot 'run_stats.py') --since $since @($SessionIds) 2>$null
        if ($LASTEXITCODE -ne 0) { return $blank }
        $parsed = $text | ConvertFrom-Json
        foreach ($name in @($blank.Keys)) { $blank[$name] = $parsed.$name }
    }
    catch { Write-Warning "Could not read run stats: $($_.Exception.Message)" }
    $blank
}

# Export-Csv -Append rejects rows when the header is older, so add missing columns first. Old rows stay blank there.
function Add-MetricColumns([string]$Path, [string[]]$Columns) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $stream = [IO.File]::Open($Path, 'Open', 'ReadWrite', 'None')
    try {
        $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8, $true, 4096, $true)
        $text = $reader.ReadToEnd(); $reader.Dispose()
        $lines = @($text -split "`r?`n" | Where-Object { $_ })
        if (-not $lines.Count) { return }
        $existing = @(($lines[0] | ConvertFrom-Csv -Header (1..200)).PSObject.Properties.Value | Where-Object { $_ })
        $missing = @($Columns | Where-Object { $existing -notcontains $_ })
        if (-not $missing.Count) { return }
        $lines[0] += ($missing | ForEach-Object { ",`"$_`"" }) -join ''
        $padding = ',' * $missing.Count
        for ($i = 1; $i -lt $lines.Count; $i++) { $lines[$i] += $padding }
        $bytes = (New-Object Text.UTF8Encoding($true)).GetPreamble() + [Text.Encoding]::UTF8.GetBytes(($lines -join "`r`n") + "`r`n")
        $stream.SetLength(0); $stream.Write($bytes, 0, $bytes.Length)
    }
    finally { $stream.Dispose() }
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
    $verifierArgs = "--setting-sources project --strict-mcp-config --model sonnet --tools Read,Grep,Glob --permission-mode dontAsk --allowedTools Read,Grep,Glob --output-format json $(Get-SchemaArg $VerifierSchema)"
    $line = ("$ClaudePrefix -p $verifierArgs --max-turns 40 --max-budget-usd $budget").Trim()
    $code = Invoke-Logged $ClaudeExe $line $prompt "$Tag-verifier.log"
    $result = Read-Result "$Tag-verifier.log"
    if ($result) { $script:VerifierUsd += [double]$result.total_cost_usd }
    if ((RepoGit $Worktree rev-parse HEAD) -ne $head -or (RepoGit $Worktree status --porcelain)) { throw 'The verifier changed the worktree.' }
    if ($code -ne 0 -or -not $result.structured_output) { return 'The verifier could not finish. Confirm your work is still complete, then report DONE again.' }
    if ($result.structured_output.verdict -eq 'PASS') {
        Invoke-Review $Tag $result $verifierArgs $head
        return $null
    }
    $script:VerifierFails++
    "An independent verifier rejected this work:`n$($result.structured_output.problems)"
}

# After a PASS, the verifier's session is resumed as a reviewer, reusing its cached reading. Its flags go to the owner
# and never fail the work, so any problem here is only a warning.
function Invoke-Review([string]$Tag, $Verified, [string]$VerifierArgs, [string]$Head) {
    try {
        if (-not $Verified.session_id) { Write-Warning 'No verifier session to review from.'; return }
        $spent = [double]$Verified.total_cost_usd
        $cap = [Math]::Min($ReviewerMaxUsd, $MaxUsd - (Get-Spent))
        if ($cap -le 0) { return }
        # Budgets may count the whole resumed session, so the cap includes what the verifier spent.
        $budget = ($spent + $cap).ToString('0.####', [Globalization.CultureInfo]::InvariantCulture)
        $line = ("$ClaudePrefix -p $VerifierArgs --resume $($Verified.session_id) --max-turns 15 --max-budget-usd $budget").Trim()
        $code = Invoke-Logged $ClaudeExe $line $ReviewerPrompt "$Tag-review.log"
        $review = Read-Result "$Tag-review.log"
        if ($review) { $script:VerifierUsd += [Math]::Max(0, [double]$review.total_cost_usd - $spent) }
        if ((RepoGit $Worktree rev-parse HEAD) -ne $Head -or (RepoGit $Worktree status --porcelain)) { throw 'The reviewer changed the worktree.' }
        if ($code -ne 0 -or -not $review.structured_output) { Write-Warning "The review did not finish (exit $code)."; return }
        $script:ReviewFlags = @($review.structured_output.owner_flags | Where-Object { $_ })
        Add-AgentReports $script:ReviewFlags 'review'
    }
    catch {
        if ($_.Exception.Message -like '*changed the worktree*') { throw }
        Write-Warning "Review skipped: $($_.Exception.Message)"
    }
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
# Agents need the game data and shared engine builds for real tests. agent-settings.json denies edits to both.
$GameDataDir = Join-Path $Repo 'GameResources'
$GameModsDir = Join-Path $Repo 'GameMods'
$SharedBuildDir = Join-Path (Split-Path $Repo -Parent) ((Split-Path $Repo -Leaf) + '-build')
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
# One file per run, so parallel lanes never rewrite each other's reports. The orchestrator deletes each once triaged.
$ReportsDir = Join-Path $Repo 'work\agent-reports'
$ReportsFile = Join-Path $ReportsDir ("$Stamp" + $(if ($Lane) { "-$Lane" }) + '.md')
# Only triaged questions. Untriaged reports stay out of the prompt to keep it small; triage removes duplicates.
$OpenQuestions = if (Test-Path $QuestionsFile) { [IO.File]::ReadAllText($QuestionsFile) } else { '' }
if (-not $OpenQuestions) { $OpenQuestions = 'None.' }
$VerifierPrompt = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'verifier.md'))
$ReviewerPrompt = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'reviewer.md'))
$ReviewFlags = @()
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
$SessionIds = @($session)
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
        $line = ("$ClaudePrefix -p --setting-sources project --strict-mcp-config --model $Model --permission-mode acceptEdits --settings `"$Settings`" --add-dir `"$ReviewDir`" --add-dir `"$GameDataDir`" --add-dir `"$GameModsDir`" --add-dir `"$SharedBuildDir`" $resume --max-turns $MaxTurnsPerRound --max-budget-usd $budget --output-format json $(Get-SchemaArg $AgentSchema)").Trim()
        $code = Invoke-Logged $ClaudeExe $line $next "$tag.log"
        Save-Work

        # total_cost_usd is cumulative across resumes of one session.
        $r = Read-Result "$tag.log"
        if ($r) {
            if ($r.session_id) { $session = $r.session_id; $SessionIds += $session }
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
            if (-not $started) { $PriorSessionUsd += $SessionUsd; $SessionUsd = 0.0; $session = [guid]::NewGuid().ToString(); $SessionIds += $session; $next = $FirstPrompt }
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
$stats = Get-RunStats
$metric = [pscustomobject]@{
    Run = $Stamp; Harness = $harness; Model = $Model; Result = $result; Rounds = $round; Turns = $Turns
    CostUsd = $cost; Minutes = $minutes; Commits = $commits.Count; Verifications = $Verifications
    CheckFails = $CheckFails; VerifierFails = $VerifierFails; Denials = $Denials; ReviewFlags = $ReviewFlags.Count
    PeakContext = $stats.PeakContext; CacheReadTokens = $stats.CacheReadTokens; OutputTokens = $stats.OutputTokens
    Messages = $stats.Messages; ToolOutputChars = $stats.ToolOutputChars
}
# The shared file can be locked, for example while it is open in a spreadsheet. Never lose the row.
$metricSaved = $false
foreach ($try in 1..12) {
    try {
        Add-MetricColumns (Join-Path $RunDir 'metrics.csv') @($metric.PSObject.Properties.Name)
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
$openCount = @(Get-ChildItem -LiteralPath $ReportsDir -Filter '*.md' -File -ErrorAction SilentlyContinue | Get-Content | Where-Object { $_ -like '- *' }).Count
$entry = @("## Run $Stamp", "- Result: $outcome", "- Branch: $Branch ($($commits.Count) commits)", "- Rounds: $round, turns: $Turns, estimated cost: `$$cost, minutes: $minutes", "- Agent reports awaiting triage: $openCount (work/agent-reports/)", "- Notes: work/notes/$Stamp.md", "- Logs: $Logs")
if ($ReviewFlags.Count) { $entry += "- Review flags for the owner ($($ReviewFlags.Count)):"; $entry += @($ReviewFlags | ForEach-Object { "  - $(([string]$_ -replace '\s+', ' ').Trim())" }) }
$entry += ''
Add-Content -LiteralPath $report -Value $entry -Encoding utf8
$entry | Write-Output
exit $exitCode
