#Requires -RunAsAdministrator
New-NetFirewallRule -DisplayName "Raed Frontend 3000" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Raed Backend 8010"  -Direction Inbound -LocalPort 8010 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
Write-Host "Firewall rules added."
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" } | Select-Object -First 1).IPAddress
Write-Host "LAN URL: http://$ip:3000"
