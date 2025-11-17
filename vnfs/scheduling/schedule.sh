#!/bin/bash

echo "=========================================="
echo "Starting Scheduling VNF with HTB queues"
echo "=========================================="

# Enable forwarding
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.forwarding=1
sysctl -w net.ipv4.conf.default.forwarding=1
sysctl -w net.ipv4.conf.all.rp_filter=0
sysctl -w net.ipv4.conf.default.rp_filter=0
sysctl -w net.ipv4.conf.eth0.rp_filter=0

if [ -n "$NEXT_HOP" ]; then
    echo "Setting up route to next hop: $NEXT_HOP"
    ip route del default 2>/dev/null || true
    ip route add default via $NEXT_HOP
    echo "Route configured!"
fi

INTERFACE="eth0"
sleep 2

echo ""
echo "Configuring HTB queues..."

# Remove existing qdiscs
tc qdisc del dev $INTERFACE root 2>/dev/null || true

# Add root qdisc
tc qdisc add dev $INTERFACE root handle 1: htb default 30
echo "✓ Root qdisc created"

# Add root class
tc class add dev $INTERFACE parent 1: classid 1:1 htb rate 100mbit ceil 100mbit
echo "✓ Root class created"

# VoIP class
tc class add dev $INTERFACE parent 1:1 classid 1:10 htb rate 10mbit ceil 20mbit prio 1
echo "✓ VoIP class created (1:10)"

# Video class
tc class add dev $INTERFACE parent 1:1 classid 1:20 htb rate 50mbit ceil 80mbit prio 2
echo "✓ Video class created (1:20)"

# Data class
tc class add dev $INTERFACE parent 1:1 classid 1:30 htb rate 20mbit ceil 100mbit prio 3
echo "✓ Data class created (1:30)"

# Add SFQ to leaf classes
tc qdisc add dev $INTERFACE parent 1:10 handle 10: sfq perturb 10
tc qdisc add dev $INTERFACE parent 1:20 handle 20: sfq perturb 10
tc qdisc add dev $INTERFACE parent 1:30 handle 30: sfq perturb 10
echo "✓ SFQ qdiscs added"

# Filters for DSCP marking
# VoIP: DSCP EF (46) = 0xB8 in TOS field
tc filter add dev $INTERFACE parent 1: protocol ip prio 1 u32 \
    match ip tos 0xb8 0xfc \
    flowid 1:10
echo "✓ VoIP filter added (DSCP=46)"

# Video: DSCP AF41 (34) = 0x88 in TOS field
tc filter add dev $INTERFACE parent 1: protocol ip prio 2 u32 \
    match ip tos 0x88 0xfc \
    flowid 1:20
echo "✓ Video filter added (DSCP=34)"

echo ""
echo "========================================"
echo "HTB Configuration Complete!"
echo "========================================"
echo ""
tc qdisc show dev $INTERFACE
echo ""
tc class show dev $INTERFACE
echo ""
tc filter show dev $INTERFACE
echo ""

# Start monitoring loop
exec > /logs/scheduling.log 2>&1

while true; do
    echo "============================================"
    date
    echo "Queue Statistics:"
    tc -s class show dev $INTERFACE
    echo ""
    sleep 5
done