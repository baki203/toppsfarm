$repo = "C:\Users\sargo\Downloads\toppsfarm"
Set-Location $repo
$claude="C:\Users\sargo\.local\bin\claude.exe"
while ($true) {
  $next = (Get-Content ORDERS.md) | Where-Object { $_ -match '^- \[ \] \d+\w* \|' } | Select-Object -First 1
  if (-not $next) { Write-Host "Warteschlange leer."; break }
  $num = [regex]::Match($next, '^- \[ \] (\d+\w*)').Groups[1].Value
  Write-Host "=== Schritt $num ===" -ForegroundColor Cyan
  & $claude -p "Lies ORDERS.md. Arbeite ausschliesslich Schritt $num. Danach STATUS.md ergaenzen (Schritt, Ergebnis, Fehler woertlich), in ORDERS.md $num auf [x] setzen, STATE.md komplett neu schreiben, max 12 Zeilen: Stand, offene Punkte, naechster Schritt. Alles committen und nach origin master pushen." --dangerously-skip-permissions *>&1 | Tee-Object -FilePath claude.log -Append
  git add -A
  git commit -m "step $num" 2>$null
  git push origin master
  Start-Sleep 60
}




