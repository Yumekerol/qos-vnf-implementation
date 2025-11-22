from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP
from netfilterqueue import NetfilterQueue
import logging
import sys
import os
import time
from threading import Lock

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/policing.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Policing-VNF')

NEXT_HOP = os.environ.get('NEXT_HOP', '10.0.0.22')


class TokenBucket:
    """Token bucket algorithm for rate limiting"""

    def __init__(self, rate, capacity):
        self.rate = rate  # bytes per second
        self.capacity = capacity  # maximum burst size
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = Lock()

    def consume(self, tokens_needed):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Check if we have enough tokens
            if tokens_needed <= self.tokens:
                self.tokens -= tokens_needed
                return True
            return False


# Traffic buckets with rate limits
buckets = {
    'voip': TokenBucket(rate=125000, capacity=250000),  # 1 Mbps
    'video': TokenBucket(rate=1250000, capacity=2500000),  # 10 Mbps
    'data': TokenBucket(rate=625000, capacity=1250000),  # 5 Mbps
    'other': TokenBucket(rate=125000, capacity=250000)  # Default 1 Mbps
}

stats = {
    'total': 0,
    'voip_passed': 0,
    'voip_dropped': 0,
    'video_passed': 0,
    'video_dropped': 0,
    'data_passed': 0,
    'data_dropped': 0,
    'other_passed': 0,
    'other_dropped': 0
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
    return 'other'


def process_packet(packet):
    try:
        stats['total'] += 1
        
        # Get packet payload
        pkt = IP(packet.get_payload())
        packet_size = len(pkt)

        # Identify traffic class
        traffic_class = get_traffic_class(pkt)
        bucket = buckets.get(traffic_class, buckets['other'])

        # Apply policing
        if bucket.consume(packet_size):
            # Pass
            stats[f'{traffic_class}_passed'] += 1
            packet.accept()
        else:
            # Drop
            stats[f'{traffic_class}_dropped'] += 1
            packet.drop()
            if stats['total'] % 100 == 0:
                logger.warning(f"Dropped {traffic_class} packet (Rate limit exceeded)")

        # Log statistics occasionally
        if stats['total'] % 100 == 0:
            logger.info(
                f"Stats: Total={stats['total']} | "
                f"VoIP: {stats['voip_passed']}/{stats['voip_dropped']} | "
                f"Video: {stats['video_passed']}/{stats['video_dropped']} | "
                f"Data: {stats['data_passed']}/{stats['data_dropped']}")

    except Exception as e:
        logger.error(f"Error processing packet: {e}")
        packet.accept()  # Default to accept on error


def main():
    logger.info("=" * 60)
    logger.info("Policing VNF Started - NFQUEUE MODE")
    logger.info("=" * 60)
    logger.info(f"Next hop: {NEXT_HOP}")
    logger.info("Rate Limits:")
    logger.info("  - VoIP:  1 Mbps (125 KB/s)")
    logger.info("  - Video: 10 Mbps (1250 KB/s)")
    logger.info("  - Data:  5 Mbps (625 KB/s)")
    logger.info("=" * 60)

    nfqueue = NetfilterQueue()
    nfqueue.bind(0, process_packet)

    try:
        nfqueue.run()
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Policing VNF Stopped")
        logger.info(f"Final Statistics: {stats}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        nfqueue.unbind()


if __name__ == "__main__":
    main()