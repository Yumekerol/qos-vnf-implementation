#!/usr/bin/env python3
import socket
import time
import threading


def udp_echo_server():
    """Simple UDP echo server for VoIP testing"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 5004))
    print("UDP VoIP server listening on port 5004")

    while True:
        data, addr = sock.recvfrom(1024)
        # Echo back the packet
        sock.sendto(data, addr)
        print(f"Echoed {len(data)} bytes to {addr}")


if __name__ == "__main__":
    udp_echo_server()