$repo = "C:\Users\sargo\Downloads\toppsfarm"
Set-Location $repo
$claude="C:\Users\sargo\.local\bin\claude.exe"
while ($true) {
  $next = (Get-Content ORDERS.md) | Where-Object { $_ -match '^- \[ \] \d+ \|' } | Select-Object -First 1
  if (-not $next) { Write-Host "Warteschlange leer."; break }
  $num = [regex]::Match($next, '^- \[ \] (\d+)').Groups[1].Value
  Write-Host "=== Schritt $num ===" -ForegroundColor Cyan
  & $claude -p "Lies ORDERS.md. Arbeite ausschliesslich Schritt $num. Danach STATUS.md ergaenzen (Schritt, Ergebnis, Fehler woertlich), in ORDERS.md $num auf [x] setzen, alles committen und nach origin master pushen." --dangerously-skip-permissions
  git add -A
  git commit -m "step $num" 2>$null
  git push origin master
  Start-Sleep 60
}

