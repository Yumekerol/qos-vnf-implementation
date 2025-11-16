#!/bin/bash

# QoS VNF Project - Automated Testing Script (Bash version)

DURATION=30
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging function
write_test_log() {
    local message="$1"
    local type="${2:-Info}"
    local timestamp=$(date +"%H:%M:%S")

    case $type in
        "Success")
            echo -e "[$timestamp] ✓ $message"
            ;;
        "Error")
            echo -e "[$timestamp] ✗ $message"
            ;;
        "Warning")
            echo -e "[$timestamp] ⚠ $message"
            ;;
        "Info")
            echo -e "[$timestamp] ℹ $message"
            ;;
        *)
            echo "[$timestamp] $message"
            ;;
    esac
}

echo "==========================================================="
echo "    QoS VNF Project - Automated Testing Script"
echo "==========================================================="
echo ""

# Check if containers are running
write_test_log "Verifying containers status..." "Info"
containers=$(docker-compose ps --services --filter "status=running")

required_containers=(
    "client_voip" "client_video" "client_data"
    "vnf_classification" "vnf_policing" "vnf_monitoring"
    "vnf_scheduling" "vnf_access_control" "server"
)

all_running=true
for container in "${required_containers[@]}"; do
    if echo "$containers" | grep -q "$container"; then
        write_test_log "Container $container : Running" "Success"
    else
        write_test_log "Container $container : Not Running" "Error"
        all_running=false
    fi
done

if [ "$all_running" = false ]; then
    write_test_log "Some containers are not running. Execute 'docker-compose up -d' first." "Error"
    exit 1
fi

echo ""

# Phase 1: Start iperf3 servers
echo "=== PHASE 1: Start Servers ==="
echo ""

write_test_log "Stopping existing iperf3 servers..." "Info"
docker exec server pkill iperf3 2>/dev/null

sleep 2

write_test_log "Starting iperf3 server for Data (TCP:5001)..." "Info"
docker exec -d server iperf3 -s -p 5001 2>/dev/null

write_test_log "Starting iperf3 server for VoIP (UDP:5004)..." "Info"
docker exec -d server iperf3 -s -p 5004 -u 2>/dev/null

write_test_log "Starting iperf3 server for Video (TCP:8080)..." "Info"
docker exec -d server iperf3 -s -p 8080 2>/dev/null

sleep 3
write_test_log "Servers started successfully!" "Success"
echo ""

# Phase 2: Connectivity Test
echo "=== PHASE 2: Connectivity Test ==="
echo ""

ping_tests=(
    "client_voip:10.0.0.100:VoIP"
    "client_video:10.0.0.100:Video"
    "client_data:10.0.0.100:Data"
)

for test in "${ping_tests[@]}"; do
    IFS=':' read -r client server name <<< "$test"
    write_test_log "Testing connectivity: $name -> Server..." "Info"

    docker exec "$client" ping -c 3 -W 2 "$server" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        write_test_log "Connectivity OK: $name" "Success"
    else
        write_test_log "Connectivity failed: $name" "Error"
    fi
done

echo ""

# Phase 3: Individual Traffic Tests
echo "=== PHASE 3: Individual Traffic Tests ==="
echo ""

# VoIP Test
write_test_log "Test 1/3: VoIP Traffic (UDP, low latency)..." "Info"
echo "  Configuration: UDP, Port 5004, 1 Mbps, 160 byte packets"
voip_result=$(docker exec client_voip iperf3 -c 10.0.0.100 -u -p 5004 -b 1M -l 160 -t $DURATION 2>&1)

if [ $? -eq 0 ]; then
    write_test_log "VoIP test completed" "Success"
    if [ "$VERBOSE" = true ]; then
        echo "$voip_result"
    fi
else
    write_test_log "VoIP test failed" "Error"
fi

sleep 2

# Video Test
write_test_log "Test 2/3: Video Traffic (TCP, high bandwidth)..." "Info"
echo "  Configuration: TCP, Port 8080, 10 Mbps"
video_result=$(docker exec client_video iperf3 -c 10.0.0.100 -p 8080 -b 10M -t $DURATION 2>&1)

if [ $? -eq 0 ]; then
    write_test_log "Video test completed" "Success"
    if [ "$VERBOSE" = true ]; then
        echo "$video_result"
    fi
else
    write_test_log "Video test failed" "Error"
fi

sleep 2

# Data Test
write_test_log "Test 3/3: Data Traffic (TCP, best effort)..." "Info"
echo "  Configuration: TCP, Port 5001, Best Effort"
data_result=$(docker exec client_data iperf3 -c 10.0.0.100 -p 5001 -t $DURATION 2>&1)

if [ $? -eq 0 ]; then
    write_test_log "Data test completed" "Success"
    if [ "$VERBOSE" = true ]; then
        echo "$data_result"
    fi
else
    write_test_log "Data test failed" "Error"
fi

echo ""

# Phase 4: Simultaneous Traffic Test
echo "=== PHASE 4: Simultaneous Traffic Test ==="
echo ""
write_test_log "Starting simultaneous clients for $DURATION seconds..." "Info"

# Start clients in background
docker exec -d client_voip iperf3 -c 10.0.0.100 -u -p 5004 -b 1M -l 160 -t $DURATION
docker exec -d client_video iperf3 -c 10.0.0.100 -p 8080 -b 10M -t $DURATION
docker exec -d client_data iperf3 -c 10.0.0.100 -p 5001 -t $DURATION

write_test_log "Waiting for test completion..." "Info"

# Wait for completion
sleep $DURATION
write_test_log "All simultaneous tests completed!" "Success"

echo ""

# Phase 5: VNF Statistics
echo "=== PHASE 5: VNF Statistics ==="
echo ""

# Classification VNF
echo "--- Classification VNF ---"
docker logs vnf_classification --tail 20 2>&1 | grep -E "Classified|Stats|packets" | tail -10
echo ""

# Policing VNF
echo "--- Policing VNF ---"
docker logs vnf_policing --tail 20 2>&1 | grep -E "POLICING|passed|dropped|rate" | tail -10
echo ""

# Monitoring VNF
echo "--- Monitoring VNF ---"
docker logs vnf_monitoring --tail 20 2>&1 | grep -E "MONITORING|throughput|jitter|packets" | tail -10
echo ""

# Scheduling VNF
echo "--- Scheduling VNF ---"
echo "Queue Statistics:"
docker exec vnf_scheduling tc -s class show dev eth0 2>&1 | grep -E "class|Sent|rate"
echo ""

# Access Control VNF
echo "--- Access Control VNF ---"
docker exec vnf_access_control iptables -L -n -v --line-numbers 2>&1 | grep -E "Chain|pkts|ACCEPT|DROP" | head -15
echo ""

# Phase 6: Saving Results
echo "=== PHASE 6: Saving Results ==="
echo ""

timestamp=$(date +"%Y%m%d_%H%M%S")
results_dir="test_results_$timestamp"

write_test_log "Creating results directory: $results_dir" "Info"
mkdir -p "$results_dir"

# Save logs
write_test_log "Copying VNF logs..." "Info"
cp -r ./logs/* "$results_dir/" 2>/dev/null || true

# Save metrics
write_test_log "Copying metrics..." "Info"
cp -r ./metrics/* "$results_dir/" 2>/dev/null || true

# Save VNF configurations
write_test_log "Saving VNF configurations..." "Info"

docker exec vnf_scheduling tc -s class show dev eth0 > "$results_dir/scheduling_stats.txt" 2>&1
docker exec vnf_access_control iptables -L -n -v > "$results_dir/firewall_rules.txt" 2>&1

# Create summary report
report_file="$results_dir/test_report.txt"
cat > "$report_file" << EOF
==========================================================
QoS VNF Project - Test Report
==========================================================
Test Date: $(date "+%Y-%m-%d %H:%M:%S")
Test Duration: $DURATION seconds
Test Type: Individual + Simultaneous Traffic Tests

==========================================================
CONTAINERS STATUS
==========================================================
$(docker-compose ps)

==========================================================
NETWORK CONFIGURATION
==========================================================
$(docker network inspect qos-vnf-project_qos_net 2>/dev/null || echo "Network not found")

==========================================================
TEST RESULTS SUMMARY
==========================================================

VoIP Test (UDP):
$voip_result

Video Test (TCP):
$video_result

Data Test (TCP):
$data_result

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
EOF

write_test_log "Report saved to: $report_file" "Success"

# Compress results
write_test_log "Compressing results..." "Info"
zip -r "$results_dir.zip" "$results_dir" > /dev/null 2>&1
write_test_log "Results compressed: $results_dir.zip" "Success"

echo ""
echo "==========================================================="
echo "    Testing Completed Successfully!"
echo "==========================================================="
echo ""
echo "Results saved in: $results_dir.zip"
echo ""
echo "To view real-time logs, use:"
echo "  docker-compose logs -f [vnf_classification|vnf_policing|vnf_monitoring]"
echo ""
echo "Press any key to close..."
read -n 1 -s