from scapy.all import *
import logging
import sys
import os
import time
import json
from collections import defaultdict
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/monitoring.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Monitoring-VNF')

NEXT_HOP = os.environ.get('NEXT_HOP', '10.0.0.23')

stats = {
    'total': 0,
    'forwarded': 0,
    'bytes': 0,
    'start_time': time.time(),
    'classes': defaultdict(lambda: {'packets': 0, 'bytes': 0})
}


def get_traffic_class(pkt):
    try:
        if pkt.haslayer(IP):
            dscp = pkt[IP].tos >> 2
            if dscp == 46:
                return 'voip'
            elif dscp == 34:
                return 'video'
            else:
                return 'data'
    except:
        pass
    return 'unknown'


def monitor_and_forward(pkt):
    try:
        stats['total'] += 1
        packet_size = len(pkt)
        stats['bytes'] += packet_size

        # Classify
        traffic_class = get_traffic_class(pkt)
        stats['classes'][traffic_class]['packets'] += 1
        stats['classes'][traffic_class]['bytes'] += packet_size

        # Forward
        send(pkt, verbose=False)
        stats['forwarded'] += 1

        # Log every 1000 packets
        if stats['total'] % 1000 == 0:
            elapsed = time.time() - stats['start_time']
            throughput = (stats['bytes'] * 8) / elapsed / 1_000_000  # Mbps

            logger.info("=" * 60)
            logger.info(f"Total: {stats['total']} packets | {stats['bytes']:,} bytes")
            logger.info(f"Throughput: {throughput:.3f} Mbps")
            logger.info(f"Classes: {dict(stats['classes'])}")
            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("Monitoring VNF started (FORWARDING MODE)")
    logger.info("=" * 60)
    logger.info(f"Next hop: {NEXT_HOP}")
    logger.info("Collecting metrics and forwarding...")
    logger.info("=" * 60)

    try:
        sniff(iface='eth0', prn=monitor_and_forward, store=0)
    except KeyboardInterrupt:
        logger.info(f"\nFinal stats: {stats}")


if __name__ == "__main__":
    main()