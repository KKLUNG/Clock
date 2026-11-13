# Build OffWorkClock.exe and assemble a folder ready to copy to another computer.
# Output: dist\OffWorkClock\  (requires: python -m pip install pyinstaller)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$out = Join-Path $PSScriptRoot 'dist\OffWorkClock'
$work = Join-Path $env:TEMP 'OffWorkClock-build'

# Start from an empty folder so files from older versions don't linger
if (Test-Path $out) { Remove-Item $out -Recurse -Force }

python -m PyInstaller --onefile --noconsole --name OffWorkClock --distpath $out --workpath $work --specpath $work --noconfirm clock.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Copy-Item README.md -Destination $out -Force

# Ship the local config (if any) with the window position reset, so it starts at the top-right of the new screen.
# Without one, the exe falls back to its built-in defaults.
if (Test-Path config.json) {
    $config = Get-Content config.json -Raw -Encoding UTF8 | ConvertFrom-Json
    $config.x = $null
    $config.y = $null
    $json = $config | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $out 'config.json'), $json + "`n", (New-Object Text.UTF8Encoding $false))
}

Write-Host "Done: $out"
