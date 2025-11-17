# test_vnfs.ps1
# Complete script to test all VNFs in the QoS project

param(
    [int]$Duration = 30,
    [switch]$Verbose
)

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "    QoS VNF Project - Automated Testing Script" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Function for colored logging
function Write-TestLog {
    param(
        [string]$Message,
        [string]$Type = "Info"
    )

    $timestamp = Get-Date -Format "HH:mm:ss"

    switch ($Type) {
        "Success" { Write-Host "[$timestamp] ✓ $Message" -ForegroundColor Green }
        "Error"   { Write-Host "[$timestamp] ✗ $Message" -ForegroundColor Red }
        "Warning" { Write-Host "[$timestamp] ⚠ $Message" -ForegroundColor Yellow }
        "Info"    { Write-Host "[$timestamp] ℹ $Message" -ForegroundColor Cyan }
        default   { Write-Host "[$timestamp] $Message" }
    }
}

# Check if containers are running
Write-TestLog "Checking container status..." "Info"
$containers = docker-compose ps --services --filter "status=running"

$requiredContainers = @(
    "client_voip", "client_video", "client_data",
    "vnf_classification", "vnf_policing", "vnf_monitoring",
    "server"
)

$allRunning = $true
foreach ($container in $requiredContainers) {
    if ($containers -contains $container) {
        Write-TestLog "Container $container : Running" "Success"
    } else {
        Write-TestLog "Container $container : Not Running" "Error"
        $allRunning = $false
    }
}

if (-not $allRunning) {
    Write-TestLog "Some containers are not running. Execute 'docker-compose up -d' first." "Error"
    exit 1
}

Write-Host ""

# Phase 1: Start iperf3 servers
Write-Host "=== PHASE 1: Starting Servers ===" -ForegroundColor Yellow
Write-Host ""

Write-TestLog "Stopping existing iperf3 servers..." "Info"
docker exec server pkill iperf3 2>$null

Start-Sleep -Seconds 2

Write-TestLog "Starting iperf3 server for Data (TCP:5001)..." "Info"
docker exec -d server iperf3 -s -p 5001 2>$null

Write-TestLog "Starting iperf3 server for VoIP (UDP:5004)..." "Info"
docker exec -d server iperf3 -s -p 5004 -u 2>$null

Write-TestLog "Starting iperf3 server for Video (TCP:8080)..." "Info"
docker exec -d server iperf3 -s -p 8080 2>$null

Start-Sleep -Seconds 3
Write-TestLog "Servers started successfully!" "Success"
Write-Host ""

# Phase 2: Connectivity Test
Write-Host "=== PHASE 2: Connectivity Test ===" -ForegroundColor Yellow
Write-Host ""

$pingTests = @(
    @{Client="client_voip"; Server="10.0.0.100"; Name="VoIP"},
    @{Client="client_video"; Server="10.0.0.100"; Name="Video"},
    @{Client="client_data"; Server="10.0.0.100"; Name="Data"}
)

foreach ($test in $pingTests) {
    Write-TestLog "Testing connectivity: $($test.Name) -> Server..." "Info"
    $pingResult = docker exec $test.Client ping -c 3 -W 2 $test.Server 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-TestLog "Connectivity OK: $($test.Name)" "Success"
    } else {
        Write-TestLog "Connectivity failed: $($test.Name)" "Error"
    }
}

Write-Host ""

# Phase 3: Individual Tests
Write-Host "=== PHASE 3: Individual Traffic Tests ===" -ForegroundColor Yellow
Write-Host ""

# VoIP Test
Write-TestLog "Test 1/3: VoIP Traffic (UDP, low latency)..." "Info"
Write-Host "  Configuration: UDP, Port 5004, 1 Mbps, 160 byte packets" -ForegroundColor Gray
$voipResult = docker exec client_voip iperf3 -c 10.0.0.100 -u -p 5004 -b 1M -l 160 -t $Duration 2>&1
function Test-VoIPTraffic {
    param($Duration = 10)

    Write-Host "Testing VoIP Traffic (UDP)..."

    # Start UDP server if not running
    $udpProcess = docker exec server bash -c "python3 /app/voip_server.py 2>/dev/null &"

    # Test with smaller packets and UDP
    $result = docker exec client_voip bash -c @"
        iperf3 -c 10.0.0.100 -u -p 5004 -b 1M -l 160 -t $Duration -i 1
"@

    return $result
}

if ($LASTEXITCODE -eq 0) {
    Write-TestLog "VoIP test completed" "Success"
    if ($Verbose) {
        Write-Host $voipResult -ForegroundColor DarkGray
    }
} else {
    Write-TestLog "VoIP test failed" "Error"
}

Start-Sleep -Seconds 2

# Video Test
Write-TestLog "Test 2/3: Video Traffic (TCP, high bandwidth)..." "Info"
Write-Host "  Configuration: TCP, Port 8080, 10 Mbps" -ForegroundColor Gray
$videoResult = docker exec client_video iperf3 -c 10.0.0.100 -p 8080 -b 10M -t $Duration 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-TestLog "Video test completed" "Success"
    if ($Verbose) {
        Write-Host $videoResult -ForegroundColor DarkGray
    }
} else {
    Write-TestLog "Video test failed" "Error"
}

Start-Sleep -Seconds 2

# Data Test
Write-TestLog "Test 3/3: Data Traffic (TCP, best effort)..." "Info"
Write-Host "  Configuration: TCP, Port 5001, Best Effort" -ForegroundColor Gray
$dataResult = docker exec client_data iperf3 -c 10.0.0.100 -p 5001 -t $Duration 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-TestLog "Data test completed" "Success"
    if ($Verbose) {
        Write-Host $dataResult -ForegroundColor DarkGray
    }
} else {
    Write-TestLog "Data test failed" "Error"
}

Write-Host ""

# Phase 4: Simultaneous Test
Write-Host "=== PHASE 4: Simultaneous Traffic Test ===" -ForegroundColor Yellow
Write-Host ""
Write-TestLog "Starting simultaneous clients for $Duration seconds..." "Info"

# Start clients in parallel
$jobs = @()

$jobs += Start-Job -Name "VoIP" -ScriptBlock {
    docker exec client_voip iperf3 -c 10.0.0.100 -u -p 5004 -b 1M -l 160 -t $using:Duration 2>&1
}

$jobs += Start-Job -Name "Video" -ScriptBlock {
    docker exec client_video iperf3 -c 10.0.0.100 -p 8080 -b 10M -t $using:Duration 2>&1
}

$jobs += Start-Job -Name "Data" -ScriptBlock {
    docker exec client_data iperf3 -c 10.0.0.100 -p 5001 -t $using:Duration 2>&1
}

Write-TestLog "Waiting for test completion..." "Info"

# Wait and show progress
$completed = 0
while ($completed -lt 3) {
    Start-Sleep -Seconds 5
    $completed = ($jobs | Where-Object { $_.State -eq "Completed" }).Count
    Write-Host "  Progress: $completed/3 tests completed" -ForegroundColor Gray
}

Write-TestLog "All simultaneous tests completed!" "Success"

# Collect results
foreach ($job in $jobs) {
    if ($Verbose) {
        Write-Host "`n--- Result: $($job.Name) ---" -ForegroundColor DarkCyan
        Receive-Job $job
    }
}

# Clean up jobs
$jobs | Remove-Job -Force

Write-Host ""

# Phase 5: VNF Verification
Write-Host "=== PHASE 5: VNF Statistics ===" -ForegroundColor Yellow
Write-Host ""

# Classification VNF
Write-Host "--- Classification VNF ---" -ForegroundColor Green
docker logs vnf_classification --tail 20 2>&1 | Select-String -Pattern "Classified|Stats|packets" | Select-Object -Last 10
Write-Host ""

# Policing VNF
Write-Host "--- Policing VNF ---" -ForegroundColor Green
docker logs vnf_policing --tail 20 2>&1 | Select-String -Pattern "POLICING|passed|dropped|rate" | Select-Object -Last 10
Write-Host ""

# Monitoring VNF
Write-Host "--- Monitoring VNF ---" -ForegroundColor Green
docker logs vnf_monitoring --tail 20 2>&1 | Select-String -Pattern "MONITORING|throughput|jitter|packets" | Select-Object -Last 10
Write-Host ""

# Scheduling VNF
Write-Host "--- Scheduling VNF ---" -ForegroundColor Green
Write-Host "Queue Statistics:" -ForegroundColor Cyan
docker exec vnf_scheduling tc -s class show dev eth0 2>&1 | Select-String -Pattern "class|Sent|rate"
Write-Host ""

# Access Control VNF
Write-Host "--- Access Control VNF ---" -ForegroundColor Green
docker exec vnf_access_control iptables -L -n -v --line-numbers 2>&1 | Select-String -Pattern "Chain|pkts|ACCEPT|DROP" | Select-Object -First 15
Write-Host ""

# Phase 6: Saving Results
Write-Host "=== PHASE 6: Saving Results ===" -ForegroundColor Yellow
Write-Host ""

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$resultsDir = "test_results_$timestamp"

Write-TestLog "Creating results directory: $resultsDir" "Info"
New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null

# Save logs
Write-TestLog "Copying VNF logs..." "Info"
Copy-Item -Path ".\logs\*" -Destination $resultsDir -Force -ErrorAction SilentlyContinue

# Save metrics
Write-TestLog "Copying metrics..." "Info"
Copy-Item -Path ".\metrics\*" -Destination $resultsDir -Force -ErrorAction SilentlyContinue

# Save VNF configurations
Write-TestLog "Saving VNF configurations..." "Info"

docker exec vnf_scheduling tc -s class show dev eth0 > "$resultsDir\scheduling_stats.txt" 2>&1
docker exec vnf_access_control iptables -L -n -v > "$resultsDir\firewall_rules.txt" 2>&1

# Create summary report
$reportFile = "$resultsDir\test_report.txt"
@"
==========================================================
QoS VNF Project - Test Report
==========================================================
Test Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Test Duration: $Duration seconds
Test Type: Individual + Simultaneous Traffic Tests

==========================================================
CONTAINERS STATUS
==========================================================
$((docker-compose ps) -join "`n")

==========================================================
NETWORK CONFIGURATION
==========================================================
$(docker network inspect qos-vnf-project_qos_net | ConvertFrom-Json | ConvertTo-Json -Depth 5)

==========================================================
TEST RESULTS SUMMARY
==========================================================

VoIP Test (UDP):
$voipResult

Video Test (TCP):
$videoResult

Data Test (TCP):
$dataResult

==========================================================
VNF STATISTICS
==========================================================

Classification VNF:
$(docker logs vnf_classification --tail 30 2>&1)

Policing VNF:
$(docker logs vnf_policing --tail 30 2>&1)

Monitoring VNF:
$(docker logs vnf_monitoring --tail 30 2>&1)

Scheduling VNF:
$(docker exec vnf_scheduling tc -s class show dev eth0 2>&1)

Access Control VNF:
$(docker exec vnf_access_control iptables -L -n -v 2>&1)

==========================================================
END OF REPORT
==========================================================
"@ | Out-File -FilePath $reportFile -Encoding UTF8

Write-TestLog "Report saved to: $reportFile" "Success"

# Compress results
Write-TestLog "Compressing results..." "Info"
Compress-Archive -Path $resultsDir -DestinationPath "$resultsDir.zip" -Force
Write-TestLog "Results compressed: $resultsDir.zip" "Success"

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "    Tests Completed Successfully!" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Results saved to: $resultsDir.zip" -ForegroundColor Green
Write-Host ""
Write-Host "To view real-time logs, use:" -ForegroundColor Yellow
Write-Host "  docker-compose logs -f [vnf_classification|vnf_policing|vnf_monitoring]" -ForegroundColor Gray
Write-Host ""