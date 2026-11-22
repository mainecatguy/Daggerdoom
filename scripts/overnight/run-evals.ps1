<#
Small repeatable baseline: read-only repo questions with known answers.
Runs each task more than once per model, then reports pass rate, flakiness, cost, and time.
Use it before and after changing a prompt, model, or harness.
It measures code navigation only. metrics.csv tracks real overnight outcomes.

Run:      .\scripts\overnight\run-evals.ps1
Compare:  .\scripts\overnight\run-evals.ps1 -Models haiku,sonnet
#>
param(
    [string[]]$Models = @('sonnet'),
    [int]$Repeats = 2,
    [int]$Parallel = 4,
    [double]$MaxUsd = 2,
    [double]$TaskMaxUsd = 0.25,
    [int]$TimeoutSeconds = 120,
    [string]$TasksFile = (Join-Path $PSScriptRoot 'evals\tasks.json'),
    [string]$RunDir,
    [string]$WorkDir,
    [string]$ClaudeExe = 'claude',
    [string]$ClaudePrefix = ''
)

# --- Setup ---
$Models = @($Models | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$Repo = (& git -C $PSScriptRoot rev-parse --show-toplevel)
if (-not $WorkDir) { $WorkDir = $Repo }
if (-not $RunDir) { $RunDir = Join-Path (Split-Path $Repo -Parent) ((Split-Path $Repo -Leaf) + '-loop') }
$Stamp = Get-Date -Format yyyyMMdd-HHmmss
$Logs = Join-Path $RunDir "evals\$Stamp"
New-Item -ItemType Directory -Force $Logs | Out-Null
$Harness = (& git -C $Repo rev-parse --short HEAD:scripts/overnight 2>$null); if (-not $Harness) { $Harness = 'uncommitted' }
$Schema = '{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"]}'.Replace('"', '\"')
# Assign first: Windows PowerShell emits a parsed JSON array as one object.
$Tasks = Get-Content $TasksFile -Raw | ConvertFrom-Json
$Tasks = @($Tasks)

$Queue = New-Object System.Collections.Queue
foreach ($model in $Models) { foreach ($task in $Tasks) { foreach ($n in 1..$Repeats) { $Queue.Enqueue([pscustomobject]@{ Model = $model; Task = $task; Attempt = $n }) } } }

# --- Grade one finished run ---
function Complete-Job($Job, [bool]$TimedOut) {
    $o = $null; try { $o = Get-Content $Job.Log -Raw -ErrorAction Stop | ConvertFrom-Json } catch {}
    $answer = if ($o) { [string]$o.structured_output.answer } else { '' }
    $cost = if ($o) { [double]$o.total_cost_usd } else { 0.0 }
    $script:Spent += $cost
    [pscustomobject]@{
        Run = $Stamp; Harness = $Harness; Model = $Job.Item.Model; Task = $Job.Item.Task.id; Attempt = $Job.Item.Attempt
        Pass = (-not $TimedOut -and $o -and -not $o.is_error -and $answer -match $Job.Item.Task.expect)
        CostUsd = [Math]::Round($cost, 5); Seconds = [Math]::Round(((Get-Date) - $Job.Started).TotalSeconds, 1)
        Turns = if ($o) { [int]$o.num_turns } else { 0 }; Answer = $answer
    }
}

# --- Run with limited parallelism and a total budget ---
$Spent = 0.0; $Running = New-Object System.Collections.ArrayList; $Rows = New-Object System.Collections.ArrayList; $id = 0
while ($Queue.Count -or $Running.Count) {
    while ($Queue.Count -and $Running.Count -lt $Parallel -and $Spent -lt $MaxUsd) {
        $item = $Queue.Dequeue(); $id++
        $log = Join-Path $Logs "$id-$($item.Model)-$($item.Task.id)-$($item.Attempt).json"
        [IO.File]::WriteAllText("$log.in", $item.Task.prompt)
        $budget = ([Math]::Min($TaskMaxUsd, $MaxUsd - $Spent)).ToString('0.####', [Globalization.CultureInfo]::InvariantCulture)
        $line = ("$ClaudePrefix -p --no-session-persistence --setting-sources project --model $($item.Model) --tools Read,Grep,Glob --permission-mode dontAsk --allowedTools Read,Grep,Glob --max-turns 12 --max-budget-usd $budget --output-format json --json-schema `"$Schema`"").Trim()
        $p = Start-Process -FilePath $ClaudeExe -ArgumentList $line -WorkingDirectory $WorkDir -NoNewWindow -PassThru -RedirectStandardInput "$log.in" -RedirectStandardOutput $log -RedirectStandardError "$log.err"
        $null = $p.Handle
        [void]$Running.Add([pscustomobject]@{ Process = $p; Item = $item; Log = $log; Started = Get-Date })
    }
    if ($Queue.Count -and $Spent -ge $MaxUsd -and -not $Running.Count) { Write-Warning "Stopped at the `$$MaxUsd eval budget. $($Queue.Count) runs skipped."; break }
    foreach ($job in @($Running)) {
        $timedOut = ((Get-Date) - $job.Started).TotalSeconds -gt $TimeoutSeconds
        if ($job.Process.HasExited -or $timedOut) {
            if ($timedOut -and -not $job.Process.HasExited) { & taskkill.exe /PID $job.Process.Id /T /F 2>$null | Out-Null } else { $timedOut = $false }
            $job.Process.WaitForExit()
            [void]$Rows.Add((Complete-Job $job $timedOut)); $Running.Remove($job)
        }
    }
    Start-Sleep -Milliseconds 200
}

# --- Save rows and print the baseline ---
$Rows | Export-Csv -LiteralPath (Join-Path $RunDir 'evals.csv') -Append -NoTypeInformation -Encoding utf8
$summary = foreach ($g in ($Rows | Group-Object Model)) {
    $flaky = @($g.Group | Group-Object Task | Where-Object { @($_.Group.Pass | Select-Object -Unique).Count -gt 1 }).Count
    [pscustomobject]@{
        Model = $g.Name; Runs = $g.Count; PassPct = [Math]::Round(100 * @($g.Group | Where-Object Pass).Count / $g.Count)
        FlakyTasks = $flaky; AvgCostUsd = [Math]::Round(($g.Group | Measure-Object CostUsd -Average).Average, 4)
        AvgSeconds = [Math]::Round(($g.Group | Measure-Object Seconds -Average).Average, 1)
    }
}
$summary | Format-Table -AutoSize | Out-String | Write-Output
$Rows | Where-Object { -not $_.Pass } | ForEach-Object { "FAILED $($_.Model) $($_.Task) #$($_.Attempt): $($_.Answer)" }
"Total estimated cost: `$$([Math]::Round($Spent, 4))"
"Details: $(Join-Path $RunDir 'evals.csv')"
