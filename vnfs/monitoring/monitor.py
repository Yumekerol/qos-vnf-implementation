from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP
from netfilterqueue import NetfilterQueue
import logging
import sys
import os
import time
from collections import defaultdict

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/monitoring.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Monitoring-VNF')

NEXT_HOP = os.environ.get('NEXT_HOP', '10.0.0.100')

stats = {
    'total': 0,
    'forwarded': 0,
    'bytes': 0,
    'start_time': time.time(),
    'classes': defaultdict(lambda: {'packets': 0, 'bytes': 0})
}


def get_traffic_class(pkt):
    """Identify traffic class from DSCP marking"""
    try:
        if pkt.haslayer(IP):
            dscp = pkt[IP].tos >> 2
            if dscp == 46:
                return 'voip'
            elif dscp == 34:
                return 'video'
            elif dscp == 0:
                return 'data'
            else:
                return 'other'
    except:
        pass
    return 'unknown'


def process_packet(packet):
    try:
        stats['total'] += 1
        
        # Get packet payload
        pkt = IP(packet.get_payload())
        packet_size = len(pkt)
        stats['bytes'] += packet_size

        # Classify traffic
        traffic_class = get_traffic_class(pkt)
        stats['classes'][traffic_class]['packets'] += 1
        stats['classes'][traffic_class]['bytes'] += packet_size

        # Forward packet (Accept)
        packet.accept()
        stats['forwarded'] += 1

        # Log every 500 packets
        if stats['total'] % 500 == 0:
            elapsed = time.time() - stats['start_time']
            throughput_mbps = (stats['bytes'] * 8) / elapsed / 1_000_000

            logger.info("=" * 60)
            logger.info(f"Total Packets: {stats['total']:,} | Bytes: {stats['bytes']:,}")
            logger.info(f"Throughput: {throughput_mbps:.2f} Mbps")
            logger.info(f"Traffic Breakdown:")
            for traffic_type, data in stats['classes'].items():
                logger.info(f"  - {traffic_type.upper()}: "
                            f"{data['packets']:,} packets | "
                            f"{data['bytes']:,} bytes")
            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error processing packet: {e}")
        packet.accept()  # Default to accept on error


def main():
    logger.info("=" * 60)
    logger.info("Monitoring VNF Started - NFQUEUE MODE")
    logger.info("=" * 60)
    logger.info(f"Next hop: {NEXT_HOP}")
    logger.info("Collecting network metrics...")
    logger.info("=" * 60)

    nfqueue = NetfilterQueue()
    nfqueue.bind(0, process_packet)

    try:
        nfqueue.run()
    except KeyboardInterrupt:
        elapsed = time.time() - stats['start_time']
        throughput_mbps = (stats['bytes'] * 8) / elapsed / 1_000_000

        logger.info("\n" + "=" * 60)
        logger.info("Monitoring VNF Stopped")
        logger.info(f"Session Duration: {elapsed:.1f} seconds")
        logger.info(f"Average Throughput: {throughput_mbps:.2f} Mbps")
        logger.info(f"Final Statistics: {dict(stats['classes'])}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        nfqueue.unbind()


if __name__ == "__main__":
    main()