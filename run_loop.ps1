$repo = "C:\Users\sargo\Downloads\toppsfarm"
Set-Location $repo
$claude = "C:\Users\sargo\.local\bin\claude.exe"
while ($true) {
  $next = (Get-Content ORDERS.md) | Where-Object { $_ -match '^- \[[ -]\] \d+\w* \|' } | Select-Object -First 1
  if (-not $next) { Write-Host "Warteschlange leer."; break }
  $num = [regex]::Match($next, '^- \[[ -]\] (\d+\w*)').Groups[1].Value
  $text = ($next -split '\|', 2)[1].Trim()
  Write-Host "=== Schritt $num ===" -ForegroundColor Cyan
  & $claude -p "Setze jetzt um, schreibe den Code, keine Analyse: $text . Danach: STATUS.md ergaenzen, in ORDERS.md $num auf [x] setzen, STATE.md neu schreiben (max 12 Zeilen), committen, nach origin master pushen. Kurz antworten." --dangerously-skip-permissions --max-turns 80 *>&1 | Tee-Object -FilePath claude.log -Append
  git add -A
  git commit -m "step $num" 2>$null
  git push origin master
  Start-Sleep 45
}
