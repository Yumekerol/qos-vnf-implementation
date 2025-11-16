Write-Host "=== Checking VNF Classification Configuration ===" -ForegroundColor Cyan

Write-Host "`n1. Classification rules:" -ForegroundColor Yellow
docker exec vnf_classification cat /app/classification_rules.json 2>$null

Write-Host "`n2. Recent classification attempts:" -ForegroundColor Yellow
docker logs vnf_classification --tail 50 | Select-String "Processing|Classified|port 5001" | Select-Object -Last 10

Write-Host "`n3. Network interfaces:" -ForegroundColor Yellow
docker exec vnf_classification ip addr show eth0