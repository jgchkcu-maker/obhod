# Builds the release installer: dist\installer\Obhod-Setup-<version>.exe
# Requires: .venv with `pip install -e .[dev]` and Inno Setup 6.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $PSScriptRoot

& "$root\.venv\Scripts\python.exe" -m PyInstaller obhod.spec --noconfirm --clean `
    --distpath "$root\dist" --workpath "$root\build"
if ($LASTEXITCODE) { throw "PyInstaller failed" }

# Paths() expects these folders next to Obhod.exe.
foreach ($name in "bin", "lists", "strategies", "data") {
    $target = Join-Path "$root\dist\Obhod" $name
    if (Test-Path $target) { Remove-Item $target -Recurse -Force }
    Copy-Item (Join-Path $root $name) $target -Recurse
}

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found: winget install JRSoftware.InnoSetup" }
& $iscc obhod.iss
if ($LASTEXITCODE) { throw "ISCC failed" }
Get-ChildItem "$root\dist\installer"
