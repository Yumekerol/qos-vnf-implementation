Write-Host "Fixing MTU issues..." -ForegroundColor Yellow

$vnfs = @("vnf_classification", "vnf_policing", "vnf_monitoring", "vnf_scheduling", "vnf_access_control")

foreach ($vnf in $vnfs) {
    docker exec $vnf ip link set dev eth0 mtu 1500 2>$null
    Write-Host "✓ $vnf MTU set to 1500" -ForegroundColor Green
}

Write-Host "MTU configuration complete!" -ForegroundColor Cyan