# Builds and startup-checks only the engines changed since Base.
param(
    [Parameter(Mandatory)][string]$Worktree,
    [Parameter(Mandatory)][string]$Base
)
$QuietRun = Join-Path $PSScriptRoot 'quiet_run.py'
Set-Location $Worktree
$changed = @(git diff --name-only $Base HEAD)

if (@($changed | Where-Object { $_ -like 'UZDoom/*' }).Count) {
    $build = '../DoomDaggerfall-build/uzdoom'
    cmake -S UZDoom -B $build -G "Visual Studio 18 2026" -A x64
    if ($LASTEXITCODE -ne 0) { Write-Output 'UZDoom configure failed.'; exit 10 }
    cmake --build $build --config Release --parallel 6
    if ($LASTEXITCODE -ne 0) { Write-Output 'UZDoom build failed.'; exit 11 }

    $common = git rev-parse --path-format=absolute --git-common-dir
    $wad = Get-ChildItem (Join-Path (Split-Path $common -Parent) 'GameResources') -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(doom2?|freedoom[12])\.wad$' } | Select-Object -First 1
    if (-not $wad) { Write-Output 'No IWAD found for the UZDoom startup check.'; exit 12 }
    $exe = (Resolve-Path "$build/Release/uzdoom.exe").Path
    $config = Join-Path (Split-Path $exe -Parent) 'check.ini'
    & python $QuietRun --timeout 120 --cwd (Split-Path $exe -Parent) -- $exe -iwad $wad.FullName -config $config -norun -nosound -stdout
    $startupCode = $LASTEXITCODE
    if ($startupCode -eq 124) { Write-Output 'UZDoom startup timed out.'; exit 13 }
    if ($startupCode -ne 1337) { Write-Output "UZDoom startup exited with $startupCode."; exit 14 }
    Write-Output 'UZDoom: build and startup passed.'
}

if (@($changed | Where-Object { $_ -like 'daggerfall-unity-master/*' }).Count) {
    $log = 'daggerfall-unity-master/Logs/cli-build.log'
    Remove-Item $log -ErrorAction SilentlyContinue
    # Windowed on purpose: batch mode fails the license check on this machine.
    & python $QuietRun --timeout 5400 --desktop -- Unity.exe -projectPath daggerfall-unity-master -buildTarget Win64 -executeMethod CliBuild.BuildWindows64 -logFile $log
    if ($LASTEXITCODE -eq 124) { Write-Output 'Unity build timed out.'; exit 20 }
    if (-not (Select-String -Path $log -SimpleMatch 'CliBuild result: Succeeded' -Quiet)) { Write-Output 'Unity build failed.'; exit 21 }
    Write-Output 'Daggerfall Unity: build passed.'
}

Write-Output 'Check complete.'
exit 0
