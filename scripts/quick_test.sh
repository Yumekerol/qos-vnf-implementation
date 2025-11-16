#!/bin/bash

# Quick VNF Chain Test - Bash version

DURATION=10

echo "========================================="
echo " Quick VNF Chain Test"
echo "========================================="
echo ""

# Start iperf3 servers
echo "1. Starting iperf3 servers..."
docker exec server pkill iperf3 2>/dev/null
sleep 1

docker exec -d server iperf3 -s -p 5001 2>/dev/null
docker exec -d server iperf3 -s -p 5004 -u 2>/dev/null
docker exec -d server iperf3 -s -p 8080 2>/dev/null

sleep 2
echo "   ✓ Servers started"

echo ""
echo "2. Testing connectivity..."

docker exec client_voip ping -c 3 -W 2 10.0.0.100 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✓ Client can reach server"
else
    echo "   ✗ Client CANNOT reach server - Check VNF chain!"
    exit 1
fi

echo ""
echo "3. Running traffic test ($DURATION seconds)..."

echo "   Testing Data traffic (TCP)..."
data_test=$(docker exec client_data iperf3 -c 10.0.0.100 -p 5001 -t $DURATION 2>&1)

if [ $? -eq 0 ]; then
    echo "   ✓ Data test completed"
    throughput=$(echo "$data_test" | grep "sender" | tail -1)
    echo "   $throughput"
else
    echo "   ✗ Data test failed"
fi

echo ""
echo "4. Checking VNF activity..."

echo "   Classification VNF:"
class_logs=$(docker logs vnf_classification --tail 10 2>&1 | grep -E "forwarded|processed")
if [ -n "$class_logs" ]; then
    echo "   ✓ Processing packets"
    echo "$class_logs" | while read -r line; do
        echo "     $line"
    done
else
    echo "   ✗ No packet processing detected"
fi

echo ""
echo "   Policing VNF:"
police_logs=$(docker logs vnf_policing --tail 10 2>&1 | grep -E "passed|dropped|processed")
if [ -n "$police_logs" ]; then
    echo "   ✓ Processing packets"
    echo "$police_logs" | while read -r line; do
        echo "     $line"
    done
else
    echo "   ✗ No packet processing detected"
fi

echo ""
echo "   Monitoring VNF:"
monitor_logs=$(docker logs vnf_monitoring --tail 10 2>&1 | grep -E "throughput|packets|forwarded")
if [ -n "$monitor_logs" ]; then
    echo "   ✓ Collecting metrics"
    echo "$monitor_logs" | while read -r line; do
        echo "     $line"
    done
else
    echo "   ✗ No metrics detected"
fi

echo ""
echo "========================================="
echo " Quick Test Complete"
echo "========================================="
echo ""
echo "If VNFs show packet processing, the chain is working!"
echo "Run full tests with: ./test_traffic.sh --duration 30"
echo ""
echo "Press any key to close..."
read -n 1 -s