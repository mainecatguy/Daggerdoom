<#
Runs one lane of goal files, in name order, through run.ps1.
Goal files are named NN.model.name.md, for example 01.opus.bridge-core.md.
Verified work lands on the lane's own branch, overnight/<Lane>. Integration and main are never touched.
Stops at the deadline, at the cost cap, or after two runs in a row without verified work.

Run: .\scripts\overnight\queue.ps1 -Lane engine -GoalDir work\queue\engine -RunDir D:\dev\DoomDaggerfall-loop
#>
param(
    [Parameter(Mandatory)][string]$Lane,
    [Parameter(Mandatory)][string]$GoalDir,
    [Parameter(Mandatory)][string]$RunDir,
    [string]$From = 'integration',
    [datetime]$Until,
    [double]$MaxUsd = 30,
    [double]$MaxUsdPerGoal = 15,
    [string]$ClaudeExe = 'claude',
    [string]$ClaudePrefix = ''
)

$Culture = [Globalization.CultureInfo]::InvariantCulture
if (-not $PSBoundParameters.ContainsKey('Until')) {
    $Until = (Get-Date).Date.AddHours(7)
    if ($Until -le (Get-Date)) { $Until = $Until.AddDays(1) }
}
$Repo = (& git -C $PSScriptRoot rev-parse --show-toplevel)
$Target = "overnight/$Lane"
$GoalDir = (Resolve-Path $GoalDir).Path
New-Item -ItemType Directory -Force $RunDir, (Join-Path $GoalDir 'done') | Out-Null
$Log = Join-Path $RunDir "queue-$Lane.log"
$Metrics = Join-Path $RunDir 'metrics.csv'

function Write-Queue([string]$Text) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$Lane] $Text"
    Add-Content -LiteralPath $Log -Value $line -Encoding utf8
    Write-Output $line
}

& git -C $Repo show-ref --verify --quiet "refs/heads/$Target"
if ($LASTEXITCODE -ne 0) {
    & git -C $Repo branch $Target $From
    if ($LASTEXITCODE -ne 0) { throw "Could not create $Target from $From." }
}

$spent = 0.0; $misses = 0
foreach ($file in (Get-ChildItem -LiteralPath $GoalDir -File -Filter '*.md' | Sort-Object Name)) {
    $hours = ($Until - (Get-Date)).TotalHours
    if ($hours -le 0) { Write-Queue 'Stopping: reached the deadline.'; break }
    $left = $MaxUsd - $spent
    if ($left -le 0.5) { Write-Queue "Stopping: reached the `$$MaxUsd cost cap."; break }

    $parts = $file.Name.Split('.')
    if ($parts.Count -lt 4) { Write-Queue "Skipping $($file.Name): expected NN.model.name.md."; continue }
    $model = $parts[1]
    $budget = [Math]::Min($left, $MaxUsdPerGoal)
    Write-Queue "Starting $($file.Name) on $model with `$$($budget.ToString('0.00', $Culture))."

    $before = @(if (Test-Path $Metrics) { Import-Csv $Metrics }).Count
    $runArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'run.ps1'),
        '-GoalFile', $file.FullName, '-RunDir', $RunDir, '-Target', $Target, '-Lane', $Lane, '-Model', $model,
        '-Hours', $hours.ToString('0.###', $Culture), '-MaxUsd', $budget.ToString('0.####', $Culture), '-ClaudeExe', $ClaudeExe)
    if ($ClaudePrefix) { $runArgs += @('-ClaudePrefix', $ClaudePrefix) }
    & powershell.exe @runArgs *>> (Join-Path $RunDir "queue-$Lane-output.log")

    $rows = @(if (Test-Path $Metrics) { Import-Csv $Metrics })
    $row = if ($rows.Count -gt $before) { $rows[-1] } else { $null }
    $result = if ($row) { $row.Result } else { 'no-metrics' }
    if ($row) { $spent += [double]::Parse($row.CostUsd, $Culture) }
    Write-Queue "Finished $($file.Name): $result. Lane spend `$$($spent.ToString('0.00', $Culture))."

    if ($result -eq 'verified') {
        $misses = 0
        Move-Item -LiteralPath $file.FullName -Destination (Join-Path $GoalDir 'done') -Force
    }
    else {
        $misses++
        if ($misses -ge 2) { Write-Queue 'Stopping: two runs in a row without verified work.'; break }
    }
}
Write-Queue 'Lane finished.'
