<#
Take-notes step, run by queue.ps1 after each card whatever its result. A Sonnet note taker files every report in
work\agent-reports\ (questions, oversights, manager notes) and moves each to triaged\. See take-notes.md.
One note taker at a time across lanes, under work\.take-notes.lock ("<pid> <ISO time>"). A lock held by a live process
younger than 20 minutes is waited for (polled every 15 s); otherwise it is taken over. Never throws: a failure is
logged and returned, so the lane carries on. Never builds or launches game programs.

Run by hand: .\scripts\overnight\take_notes.ps1 -Lane manual -RunDir D:\dev\DoomDaggerfall-loop
#>
param(
    [string]$Lane = 'manual',
    [Parameter(Mandatory)][string]$RunDir,
    [string]$WorkDir,                # default: <main checkout>\work. Tests point it at a scratch copy.
    [double]$MaxUsd = 1,
    [int]$TimeoutMinutes = 10,
    [int]$LockStaleMinutes = 20,
    [int]$PollSeconds = 15,
    [string]$ClaudeExe = 'claude',
    [string]$ClaudePrefix = ''
)

$Culture = [Globalization.CultureInfo]::InvariantCulture
$Repo = ((& git -C $PSScriptRoot rev-parse --show-toplevel) -replace '/', '\')
if (-not $WorkDir) { $WorkDir = Join-Path $Repo 'work' }
$WorkDir = [IO.Path]::GetFullPath($WorkDir)
$Reports = Join-Path $WorkDir 'agent-reports'
$LockFile = Join-Path $WorkDir '.take-notes.lock'
$Stamp = Get-Date -Format yyyyMMdd-HHmmss
$LogDir = Join-Path $RunDir 'take-notes'
New-Item -ItemType Directory -Force $LogDir | Out-Null
$Log = Join-Path $LogDir "$Stamp-$Lane-$PID.log"
$StepLog = Join-Path $RunDir 'take-notes.log'
$Me = "$PID $((Get-Date).ToString('o'))"

function Write-Step([string]$Text) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$Lane] take-notes: $Text"
    try { Add-Content -LiteralPath $StepLog -Value $line -Encoding utf8 } catch { }
    Write-Output $line
}

# Returns once this process holds the lock. Its only output is log lines.
function Enter-NotesLock {
    $misses = 0; $last = ''
    while ($true) {
        $script:Me = "$PID $((Get-Date).ToString('o'))"   # the lock's age counts from when it is taken
        try {
            $s = [IO.File]::Open($LockFile, 'CreateNew', 'Write', 'None')
            $b = [Text.Encoding]::ASCII.GetBytes($Me); $s.Write($b, 0, $b.Length); $s.Dispose()
            return
        }
        catch { }
        $text = try { [IO.File]::ReadAllText($LockFile).Trim() } catch { $null }
        if ($null -eq $text) {   # released between our two calls, or the lock cannot be made at all
            if (++$misses -ge 50) { throw "cannot create or read $LockFile" }
            Start-Sleep -Milliseconds 200; continue
        }
        $holder = 0; $since = [datetime]::MinValue
        $parts = $text -split '\s+', 2
        $okPid = [int]::TryParse($parts[0], [ref]$holder)
        $okTime = $parts.Count -eq 2 -and [datetime]::TryParse($parts[1], $Culture, [Globalization.DateTimeStyles]::RoundtripKind, [ref]$since)
        $alive = $okPid -and $holder -ne $PID -and [bool](Get-Process -Id $holder -ErrorAction SilentlyContinue)
        $young = $okTime -and ((Get-Date) - $since).TotalMinutes -lt $LockStaleMinutes
        if ($alive -and $young) {
            if ($text -ne $last) { Write-Step "waiting for pid $holder (lock from $($parts[1]))"; $last = $text }
            Start-Sleep -Seconds $PollSeconds
            continue
        }
        # Take over: overwrite, then confirm after a moment, in case another waiter took it over at the same time.
        Write-Step "taking over lock '$text' (alive=$alive, young=$young)"
        try { [IO.File]::WriteAllText($LockFile, $Me) } catch { Start-Sleep -Seconds 1; continue }
        Start-Sleep -Seconds 2
        $now = try { [IO.File]::ReadAllText($LockFile).Trim() } catch { '' }
        if ($now -eq $Me) { return }
    }
}

function Exit-NotesLock {
    try {
        $now = [IO.File]::ReadAllText($LockFile).Trim()
        if ($now -eq $Me) { Remove-Item -LiteralPath $LockFile -Force }
        else { Write-Step "lock no longer ours at release ('$now'), left in place" }
    }
    catch { }
}

$held = $false
try {
    . (Join-Path $PSScriptRoot 'lane_job.ps1')
    if (-not @(Get-ChildItem -LiteralPath $Reports -File -Filter '*.md' -ErrorAction SilentlyContinue).Count) {
        Write-Step 'no reports to file'; return
    }
    Enter-NotesLock; $held = $true
    Write-Step "lock held ($Me)"
    # Recheck under the lock: the previous holder may have filed everything.
    if (-not @(Get-ChildItem -LiteralPath $Reports -File -Filter '*.md' -ErrorAction SilentlyContinue).Count) {
        Write-Step 'no reports left to file'; return
    }
    New-Item -ItemType Directory -Force (Join-Path $Reports 'triaged'), (Join-Path $WorkDir 'oversights') | Out-Null

    $prompt = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'take-notes.md')).
        Replace('{{REPORTS}}', $Reports).Replace('{{WORK}}', $WorkDir).
        Replace('{{DECISIONS}}', (Join-Path $Repo 'gamedesign\decisions.md'))
    $in = "$Log.in"; [IO.File]::WriteAllText($in, $prompt, (New-Object Text.UTF8Encoding($false)))
    # Edits are confined to the work folder; the shell may only list, read, append, create folders and move files.
    $w = ($WorkDir -replace '\\', '/') -replace '^([A-Za-z]):', '//$1'
    $allowed = "Read,Grep,Glob,Edit($w/**),PowerShell(Add-Content *),PowerShell(Move-Item *),PowerShell(Get-ChildItem *),PowerShell(Test-Path *),PowerShell(Get-Content *),PowerShell(Select-String *),PowerShell(New-Item *)"
    $budget = $MaxUsd.ToString('0.####', $Culture)
    $line = ("$ClaudePrefix -p --setting-sources project --strict-mcp-config --model sonnet --tools Read,Grep,Glob,Edit,PowerShell --permission-mode dontAsk --allowedTools `"$allowed`" --add-dir `"$WorkDir`" --max-turns 80 --max-budget-usd $budget --output-format json").Trim()

    $child = Start-LaneChild $ClaudeExe $line $Repo $in $Log "$Log.err"
    $p = $child.Process
    try {
        if (-not $p.WaitForExit($TimeoutMinutes * 60000)) {
            try { $p.Kill() } catch { }; $null = $p.WaitForExit(10000)
            Write-Step "timed out after $TimeoutMinutes minutes (log $Log)"; return
        }
        $p.WaitForExit(); $code = $p.ExitCode
    }
    finally { $null = @(Stop-LaneJob $child.Job) }

    $r = try { Get-Content -LiteralPath $Log -Raw -ErrorAction Stop | ConvertFrom-Json } catch { $null }
    $cost = if ($r) { ([double]$r.total_cost_usd).ToString('0.00', $Culture) } else { '?' }
    $denied = if ($r) { @($r.permission_denials).Count } else { '?' }
    $text = if ($r -and $r.result) { ([string]$r.result -replace '\s+', ' ').Trim() } else { '(no result)' }
    $left = @(Get-ChildItem -LiteralPath $Reports -File -Filter '*.md' -ErrorAction SilentlyContinue).Count
    Write-Step "exit $code, `$$cost, denials $denied, $left left in inbox: $text (log $Log)"
}
catch { Write-Step "failed: $($_.Exception.Message)" }
finally { if ($held) { Exit-NotesLock } }
