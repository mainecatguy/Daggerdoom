<#
Overnight supervisor. Runs the engine and dungeon lanes from work\queue at the same time, outside any chat.
Keeps the PC awake, restarts a crashed lane once, and writes work\queue\morning.md.
Verified work lands on overnight/<lane>. Integration and main are never touched.

Run from a normal PowerShell window and leave it open:
    powershell -ExecutionPolicy Bypass -File D:\dev\DoomDaggerfall\scripts\overnight\overnight.ps1
#>
param(
    [datetime]$Until,
    [double]$MaxUsdPerLane = 30,
    [double]$MaxUsdPerGoal = 10,
    [string]$QueueRoot,
    [string]$EngineRunDir = 'D:\dev\DoomDaggerfall-loop',
    [string]$DungeonRunDir = 'D:\dev\DoomDaggerfall-loop\lane-dungeon',
    [string]$LaneSuffix = '',
    [string]$ClaudeExe = 'claude',
    [string]$ClaudePrefix = '',
    [int]$PollSeconds = 15
)

$Culture = [Globalization.CultureInfo]::InvariantCulture
$Repo = (& git -C $PSScriptRoot rev-parse --show-toplevel)
if (-not $QueueRoot) { $QueueRoot = Join-Path $Repo 'work\queue' }
if (-not $PSBoundParameters.ContainsKey('Until')) {
    $Until = (Get-Date).Date.AddHours(7)
    if ($Until -le (Get-Date)) { $Until = $Until.AddDays(1) }
}
$StartStamp = Get-Date -Format yyyyMMdd-HHmmss
$Morning = Join-Path $QueueRoot 'morning.md'

Add-Type -Namespace Doomerfall -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);'
$ES_CONTINUOUS = [uint32]2147483648; $ES_SYSTEM_REQUIRED = [uint32]1

function Get-Runs($Lane) {
    $file = Join-Path $Lane.RunDir 'metrics.csv'
    @(if (Test-Path $file) { Import-Csv $file | Where-Object { $_.Run -ge $StartStamp } })
}

function Get-Spend($Lane) {
    $sum = 0.0
    foreach ($r in (Get-Runs $Lane)) { $sum += [double]::Parse($r.CostUsd, $Culture) }
    $sum
}

function Get-LogCount($Lane) {
    if (Test-Path $Lane.Log) { @(Get-Content -LiteralPath $Lane.Log).Count } else { 0 }
}

function Start-Lane($Lane) {
    $Lane.LogOffset = Get-LogCount $Lane
    $left = $MaxUsdPerLane - (Get-Spend $Lane)
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$(Join-Path $PSScriptRoot 'queue.ps1')`"",
        '-Lane', $Lane.Name, '-GoalDir', "`"$($Lane.GoalDir)`"", '-RunDir', "`"$($Lane.RunDir)`"",
        '-Until', "`"$($Until.ToString('s'))`"", '-MaxUsd', $left.ToString('0.####', $Culture),
        '-MaxUsdPerGoal', $MaxUsdPerGoal.ToString('0.####', $Culture), '-ClaudeExe', "`"$ClaudeExe`"")
    if ($ClaudePrefix) { $a += @('-ClaudePrefix', "`"$ClaudePrefix`"") }
    $Lane.Process = Start-Process powershell.exe -ArgumentList $a -WindowStyle Hidden -PassThru
    $null = $Lane.Process.Handle
    $Lane.State = 'running'
    Write-Output "$(Get-Date -Format HH:mm:ss) [$($Lane.Name)] started, process $($Lane.Process.Id)"
}

# A crashed lane can leave run.ps1 and Claude running. They must stop before the worktree is reused.
function Stop-Descendants([int]$ParentId) {
    foreach ($c in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId")) {
        Stop-Descendants ([int]$c.ProcessId)
        Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Save-CrashedWork($Lane) {
    $wt = Join-Path $Lane.RunDir 'worktree'
    if (-not (Test-Path $wt)) { return }
    if (& git -C $wt status --porcelain) {
        & git -C $wt add -A
        & git -C $wt commit -q -m 'overnight: save work after a lane crash'
    }
}

function Write-Morning {
    $o = @('# Overnight report', '', "Started $StartStamp. Updated $(Get-Date -Format 'yyyy-MM-dd HH:mm'). Costs are estimates.", '',
        'Verified work is on the `overnight/<lane>` branches. Nothing was merged into `integration` or `main`.', '')
    foreach ($l in $Lanes) {
        $branch = "overnight/$($l.Name)"
        $commits = & git -C $Repo rev-list --count "integration..$branch" 2>$null
        $done = @(Get-ChildItem -LiteralPath (Join-Path $l.GoalDir 'done') -File -ErrorAction SilentlyContinue | ForEach-Object Name)
        $left = @(Get-ChildItem -LiteralPath $l.GoalDir -File -Filter '*.md' -ErrorAction SilentlyContinue | ForEach-Object Name)
        $o += "## $($l.Name) lane: $($l.State)", '',
            "- Branch: ``$branch`` ($commits commits ahead of integration)",
            "- Estimated spend: `$$((Get-Spend $l).ToString('0.00', $Culture))",
            "- Restarts after a crash: $($l.Restarts)",
            "- Goals finished: $(if ($done.Count) { $done -join ', ' } else { 'none' })",
            "- Goals not finished: $(if ($left.Count) { $left -join ', ' } else { 'none' })",
            "- Run details: ``$(Join-Path $l.RunDir 'report.md')``", '',
            '| Run | Model | Result | Cost | Minutes |', '|---|---|---|---:|---:|'
        foreach ($r in (Get-Runs $l)) { $o += "| $($r.Run) | $($r.Model) | $($r.Result) | `$$($r.CostUsd) | $($r.Minutes) |" }
        $o += ''
    }
    $reports = Join-Path $Repo 'work\agent-reports.md'
    if (Test-Path $reports) { $o += '## Agent questions and reports', '', 'See `work/agent-reports.md`.', '' }
    [IO.File]::WriteAllText($Morning, ($o -join "`n"), (New-Object Text.UTF8Encoding($false)))
}

$Lanes = @(
    @{ Name = "engine$LaneSuffix"; GoalDir = (Resolve-Path (Join-Path $QueueRoot 'engine')).Path; RunDir = $EngineRunDir },
    @{ Name = "dungeon$LaneSuffix"; GoalDir = (Resolve-Path (Join-Path $QueueRoot 'dungeon')).Path; RunDir = $DungeonRunDir }
)
foreach ($l in $Lanes) {
    New-Item -ItemType Directory -Force $l.RunDir | Out-Null
    $l.Log = Join-Path $l.RunDir "queue-$($l.Name).log"
    $l.Restarts = 0; $l.LogOffset = 0; $l.State = 'waiting'; $l.Process = $null
}

[void][Doomerfall.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
try {
    Write-Output "Overnight run until $($Until.ToString('yyyy-MM-dd HH:mm')). Leave this window open."
    # Staggered so the two lanes never create the same branch name in the same second.
    foreach ($l in $Lanes) { Start-Lane $l; Start-Sleep -Seconds 2 }
    Write-Morning

    while (@($Lanes | Where-Object { $_.State -eq 'running' }).Count) {
        Start-Sleep -Seconds $PollSeconds
        [void][Doomerfall.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
        foreach ($l in @($Lanes | Where-Object { $_.State -eq 'running' -and $_.Process.HasExited })) {
            $lines = if (Test-Path $l.Log) { @(Get-Content -LiteralPath $l.Log | Select-Object -Skip $l.LogOffset) } else { @() }
            if (@($lines | Where-Object { $_ -like '*Lane finished.' }).Count) {
                $l.State = 'finished'
                Write-Output "$(Get-Date -Format HH:mm:ss) [$($l.Name)] finished"
            }
            else {
                Stop-Descendants $l.Process.Id
                Save-CrashedWork $l
                if ($l.Restarts -lt 1 -and (Get-Date) -lt $Until) {
                    $l.Restarts++
                    Write-Output "$(Get-Date -Format HH:mm:ss) [$($l.Name)] crashed, restarting once"
                    Start-Lane $l
                }
                else {
                    $l.State = 'crashed'
                    Write-Output "$(Get-Date -Format HH:mm:ss) [$($l.Name)] crashed, not restarting"
                }
            }
            Write-Morning
        }
    }
}
finally {
    [void][Doomerfall.Power]::SetThreadExecutionState($ES_CONTINUOUS)
    Write-Morning
}
Write-Output "Done. Report: $Morning"
