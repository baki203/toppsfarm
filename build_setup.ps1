# BakiAIOSetup bauen: EXE (onefile) + Laufzeitdateien + Leer-Ordner + Zip.
# Nutzt das venv in .venv. Setup-Ordner bleibt liegen.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { throw "venv python fehlt: $VenvPy" }
Set-Location $Root

# 1) EXE bauen (onefile via BakiAIO.spec -> dist\BakiAIO.exe)
# stderr der nativen EXE zusammenfuehren, sonst wirft NativeCommandError bei "Stop".
& $VenvPy -m PyInstaller --noconfirm --clean "BakiAIO.spec" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen (Exit $LASTEXITCODE)" }
$Exe = Join-Path $Root "dist\BakiAIO.exe"
if (-not (Test-Path $Exe)) { throw "dist\BakiAIO.exe fehlt" }

# 2) frisches Setup-Verzeichnis
$Setup = Join-Path $Root "dist\BakiAIOSetup"
if (Test-Path $Setup) { Remove-Item -Recurse -Force $Setup }
New-Item -ItemType Directory -Force -Path $Setup | Out-Null

# 3) Inhalt: EXE, settings.json (aus example), leere Laufzeitdateien, Leer-Ordner
Copy-Item $Exe (Join-Path $Setup "BakiAIO.exe")
Copy-Item (Join-Path $Root "BakiAIO\settings.example.json") (Join-Path $Setup "settings.json")
New-Item -ItemType File -Force -Path (Join-Path $Setup "crashlog.log")   | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $Setup "FirstNames.txt") | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $Setup "LastNames.txt")  | Out-Null
foreach ($d in @("accounts", "proxies", "Address Toolbox")) {
    $dir = Join-Path $Setup $d
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    New-Item -ItemType File -Force -Path (Join-Path $dir ".gitkeep") | Out-Null
}

# 4) kein Quellmuell im Setup (keine .md/.py/yaml/config)
Get-ChildItem -Path $Setup -Recurse -Include *.md,*.py,*.yaml,*.yml -File -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
$cfg = Join-Path $Setup "config"
if (Test-Path $cfg) { Remove-Item -Recurse -Force $cfg }

# 5) Zip-Variante (Setup-Ordner bleibt liegen)
$Zip = Join-Path $Root "dist\BakiAIOSetup.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $Setup "*") -DestinationPath $Zip

Write-Host "Setup fertig: $Setup  +  $Zip"