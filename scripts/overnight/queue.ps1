<#
Runs one lane of goal files, in name order, through run.ps1.
Goal files are named NN.model.name.md, for example 01.opus.bridge-core.md.
Verified work lands on the lane's own branch, overnight/<Lane>. Integration and main are never touched.
Runs until its goals are done, the cost cap is reached, or two runs in a row fail. -Until is an optional deadline.

Run: .\scripts\overnight\queue.ps1 -Lane engine -GoalDir work\queue\engine -RunDir D:\dev\DoomDaggerfall-loop
#>
param(
    [Parameter(Mandatory)][string]$Lane,
    [Parameter(Mandatory)][string]$GoalDir,
    [Parameter(Mandatory)][string]$RunDir,
    [string]$From = 'integration',
    [datetime]$Until,
    [double]$MaxUsd = 30,
    [double]$MaxUsdPerGoal = 10,
    [string]$ClaudeExe = 'claude',
    [string]$ClaudePrefix = ''
)

$Culture = [Globalization.CultureInfo]::InvariantCulture
if (-not $PSBoundParameters.ContainsKey('Until')) {
    $Until = [datetime]::MaxValue
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
    $hours = [Math]::Min(($Until - (Get-Date)).TotalHours, 168)
    if ($hours -le 0) { Write-Queue 'Stopping: reached the deadline.'; break }
    $left = $MaxUsd - $spent
    if ($left -le 0.5) { Write-Queue "Stopping: reached the `$$MaxUsd cost cap."; break }

    $parts = $file.Name.Split('.')
    if ($parts.Count -lt 4) { Write-Queue "Skipping $($file.Name): expected NN.model.name.md."; continue }
    $model = $parts[1]
    $budget = [Math]::Min($left, $MaxUsdPerGoal)
    Write-Queue "Starting $($file.Name) on $model with `$$($budget.ToString('0.00', $Culture))."

    $runStart = Get-Date -Format yyyyMMdd-HHmmss
    $runArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'run.ps1'),
        '-GoalFile', $file.FullName, '-RunDir', $RunDir, '-Target', $Target, '-Lane', $Lane, '-Model', $model,
        '-Hours', $hours.ToString('0.###', $Culture), '-MaxUsd', $budget.ToString('0.####', $Culture), '-MaxFailures', '28', '-ClaudeExe', $ClaudeExe)
    if ($ClaudePrefix) { $runArgs += @('-ClaudePrefix', $ClaudePrefix) }
    & powershell.exe @runArgs *>> (Join-Path $RunDir "queue-$Lane-output.log")

    $runCode = $LASTEXITCODE
    $rows = @(Get-ChildItem -LiteralPath $RunDir -Filter 'metrics*.csv' -File | ForEach-Object {
            try { Import-Csv -LiteralPath $_.FullName -ErrorAction Stop } catch { }
        } | Where-Object { $_.Run -ge $runStart } | Sort-Object Run)
    $row = if ($rows.Count) { $rows[-1] } else { $null }
    # run.ps1 exits 0 only for verified work, so a missing row cannot turn a pass into a failure.
    $result = if ($row) { $row.Result } elseif ($runCode -eq 0) { 'verified' } else { 'no-metrics' }
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
