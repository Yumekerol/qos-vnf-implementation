echo "=========================================="
echo "Starting Scheduling VNF with HTB queues"
echo "=========================================="

echo "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.forwarding=1
sysctl -w net.ipv4.conf.default.forwarding=1

sysctl -w net.ipv4.conf.all.rp_filter=0
sysctl -w net.ipv4.conf.default.rp_filter=0
sysctl -w net.ipv4.conf.eth0.rp_filter=0

sysctl -w net.ipv4.conf.all.proxy_arp=1

sysctl -w net.ipv4.conf.all.send_redirects=0
sysctl -w net.ipv4.conf.eth0.send_redirects=0

echo "IP forwarding enabled!"

if [ -n "$NEXT_HOP" ]; then
    echo "Setting up route to next hop: $NEXT_HOP"
    ip route del default 2>/dev/null || true
    ip route add default via $NEXT_HOP
    echo "Route configured!"
fi

INTERFACE="eth0"

sleep 2

echo ""
echo "Configuring HTB queues for traffic prioritization..."

tc qdisc del dev $INTERFACE root 2>/dev/null || true

tc qdisc add dev $INTERFACE root handle 1: htb default 30

tc class add dev $INTERFACE parent 1: classid 1:1 htb rate 100mbit ceil 100mbit

# Class 1:10 - VoIP (EF)
# Guaranteed: 10 Mbps, Can burst to: 20 Mbps
tc class add dev $INTERFACE parent 1:1 classid 1:10 htb rate 10mbit ceil 20mbit prio 1

# Class 1:20 - Video (AF41)
# Guaranteed: 50 Mbps, Can burst to: 80 Mbps
tc class add dev $INTERFACE parent 1:1 classid 1:20 htb rate 50mbit ceil 80mbit prio 2

# Class 1:30 - Data (BE)
# Guaranteed: 20 Mbps, Can burst to: 100 Mbps (use remaining bandwidth)
tc class add dev $INTERFACE parent 1:1 classid 1:30 htb rate 20mbit ceil 100mbit prio 3

# Add SFQ (Stochastic Fairness Queueing) to leaf classes for fairness
tc qdisc add dev $INTERFACE parent 1:10 handle 10: sfq perturb 10
tc qdisc add dev $INTERFACE parent 1:20 handle 20: sfq perturb 10
tc qdisc add dev $INTERFACE parent 1:30 handle 30: sfq perturb 10

# Filter for VoIP (DSCP EF = 46 = 0xB8 in TOS field)
tc filter add dev $INTERFACE parent 1: protocol ip prio 1 u32 \
    match ip tos 0xb8 0xfc \
    flowid 1:10

# Filter for Video (DSCP AF41 = 34 = 0x88 in TOS field)
tc filter add dev $INTERFACE parent 1: protocol ip prio 2 u32 \
    match ip tos 0x88 0xfc \
    flowid 1:20


echo ""
echo "HTB queue configuration complete!"
echo ""
echo "Queue Configuration:"
echo "  Class 1:10 (VoIP):  10 Mbps guaranteed, 20 Mbps ceiling, priority 1"
echo "  Class 1:20 (Video): 50 Mbps guaranteed, 80 Mbps ceiling, priority 2"
echo "  Class 1:30 (Data):  20 Mbps guaranteed, 100 Mbps ceiling, priority 3"
echo ""

echo "Current qdisc configuration:"
tc qdisc show dev $INTERFACE

echo ""
echo "Current class configuration:"
tc class show dev $INTERFACE

echo ""
echo "Current filter configuration:"
tc filter show dev $INTERFACE

echo ""
echo "=========================================="
echo "Scheduling VNF ready!"
echo "=========================================="

exec > /logs/scheduling.log 2>&1

while true; do
    echo "============================================"
    date
    echo "Queue Statistics:"
    tc -s class show dev $INTERFACE
    echo ""
    echo "Queue Discipline Statistics:"
    tc -s qdisc show dev $INTERFACE
    echo ""
    sleep 5
done