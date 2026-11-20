$repo = "C:\Users\sargo\Downloads\toppsfarm"
Set-Location $repo
$claude = "C:\Users\sargo\.local\bin\claude.exe"
while ($true) {
  $lines = Get-Content ORDERS.md
  $idx = -1
  for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^- \[[ -]\] \d+\w* \|') { $idx = $i; break } }
  if ($idx -lt 0) { Write-Host "Warteschlange leer."; break }
  $num = [regex]::Match($lines[$idx], '^- \[[ -]\] (\d+\w*)').Groups[1].Value
  $text = ($lines[$idx] -split '\|', 2)[1].Trim()
  Write-Host "=== Schritt $num ===" -ForegroundColor Cyan
  & $claude -p "Schreibe den Code fuer: $text" --dangerously-skip-permissions --max-turns 60 *>&1 | Tee-Object -FilePath claude.log -Append
  $lines[$idx] = ($lines[$idx] -replace '^- \[[ -]\]', '- [x]')
  $lines | Set-Content ORDERS.md -Encoding utf8
  Add-Content STATUS.md "## Schritt $num - $(Get-Date -Format 'yyyy-MM-dd HH:mm') - automatisch abgehakt, siehe claude.log"
  git add -A
  git commit -m "step $num" 2>$null
  git push origin master 2>$null
  Start-Sleep 20
}
