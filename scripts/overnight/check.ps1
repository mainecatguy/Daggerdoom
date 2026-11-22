# Builds and startup-checks only the engines changed since Base.
param(
    [Parameter(Mandatory)][string]$Worktree,
    [Parameter(Mandatory)][string]$Base
)
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
    $p = Start-Process $exe -WorkingDirectory (Split-Path $exe -Parent) -PassThru -ArgumentList @('-iwad', "`"$($wad.FullName)`"", '-config', "`"$config`"", '-norun', '-nosound', '-stdout')
    $null = $p.Handle
    if (-not $p.WaitForExit(120000)) { & taskkill.exe /PID $p.Id /T /F | Out-Null; Write-Output 'UZDoom startup timed out.'; exit 13 }
    if ($p.ExitCode -ne 1337) { Write-Output "UZDoom startup exited with $($p.ExitCode)."; exit 14 }
    Write-Output 'UZDoom: build and startup passed.'
}

if (@($changed | Where-Object { $_ -like 'daggerfall-unity-master/*' }).Count) {
    $log = 'daggerfall-unity-master/Logs/cli-build.log'
    Remove-Item $log -ErrorAction SilentlyContinue
    # Windowed on purpose: batch mode fails the license check on this machine.
    $p = Start-Process Unity.exe -PassThru -ArgumentList "-projectPath daggerfall-unity-master -buildTarget Win64 -executeMethod CliBuild.BuildWindows64 -logFile $log"
    $null = $p.Handle
    if (-not $p.WaitForExit(5400000)) { & taskkill.exe /PID $p.Id /T /F | Out-Null; Write-Output 'Unity build timed out.'; exit 20 }
    if (-not (Select-String -Path $log -SimpleMatch 'CliBuild result: Succeeded' -Quiet)) { Write-Output 'Unity build failed.'; exit 21 }
    Write-Output 'Daggerfall Unity: build passed.'
}

Write-Output 'Check complete.'
exit 0
