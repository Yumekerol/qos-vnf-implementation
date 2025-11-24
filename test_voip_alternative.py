#!/usr/bin/env python3
"""
Alternative VoIP traffic generator using Scapy
Use this if iperf3 UDP continues to fail
"""

from scapy.all import *
import time
import sys


def generate_voip_traffic(dest_ip, dest_port, duration, packet_rate):
    """
    Generate VoIP-like UDP traffic using Scapy

    Args:
        dest_ip: Destination IP address
        dest_port: Destination UDP port
        duration: Test duration in seconds
        packet_rate: Packets per second (50 for VoIP = 20ms intervals)
    """

    print("=" * 60)
    print("VoIP Traffic Generator (Scapy-based)")
    print("=" * 60)
    print(f"Destination: {dest_ip}:{dest_port}")
    print(f"Duration: {duration} seconds")
    print(f"Packet rate: {packet_rate} pps (interval: {1000 / packet_rate:.1f}ms)")
    print(f"Packet size: 160 bytes")
    print(f"Target bandwidth: ~{packet_rate * 160 * 8 / 1000:.1f} Kbps")
    print("=" * 60)

    # VoIP packet characteristics
    payload_size = 160  # G.711 codec: 160 bytes per packet
    interval = 1.0 / packet_rate  # 0.02s for 50pps

    packets_sent = 0
    start_time = time.time()

    try:
        while (time.time() - start_time) < duration:
            # Create UDP packet with payload
            packet = IP(dst=dest_ip) / UDP(sport=12345, dport=dest_port) / Raw(load=b'V' * payload_size)

            # Send packet
            send(packet, verbose=False)
            packets_sent += 1

            # Progress indicator
            if packets_sent % 50 == 0:
                elapsed = time.time() - start_time
                print(f"\rSent {packets_sent} packets in {elapsed:.1f}s...", end='', flush=True)

            # Wait for next packet
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    # Statistics
    elapsed = time.time() - start_time
    actual_rate = packets_sent / elapsed
    actual_bandwidth = (packets_sent * payload_size * 8) / elapsed / 1000  # Kbps

    print("\n")
    print("=" * 60)
    print("VoIP Traffic Generation Complete")
    print("=" * 60)
    print(f"Duration: {elapsed:.2f} seconds")
    print(f"Packets sent: {packets_sent}")
    print(f"Actual rate: {actual_rate:.1f} pps")
    print(f"Actual bandwidth: {actual_bandwidth:.1f} Kbps")
    print(f"Total data: {packets_sent * payload_size / 1024:.2f} KB")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_voip_alternative.py <duration_seconds>")
        print("\nExample:")
        print("  python test_voip_alternative.py 30")
        sys.exit(1)

    # Configuration
    DEST_IP = "10.0.0.100"
    DEST_PORT = 5004
    DURATION = int(sys.argv[1])
    PACKET_RATE = 50  # 50 packets/sec = 20ms interval (typical for VoIP)

    # Check if running as root (required for raw sockets)
    if os.geteuid() != 0:
        print("Error: This script requires root privileges")
        print("Run with: sudo python test_voip_alternative.py <duration>")
        sys.exit(1)

    generate_voip_traffic(DEST_IP, DEST_PORT, DURATION, PACKET_RATE)