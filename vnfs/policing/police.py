from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP
import logging
import sys
import os
import time
from threading import Lock

logging.basicConfig(
    level=logging.DEBUG,  # MUDAR para DEBUG
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
}

stats = {
    'total': 0,
    'passed': 0,
    'dropped': 0,
    'voip_passed': 0,
    'voip_dropped': 0,
    'video_passed': 0,
    'video_dropped': 0,
    'data_passed': 0,
    'data_dropped': 0,
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
            else:
                return 'data'
    except:
        pass
    return 'data'


def police_and_forward(pkt):
    try:
        stats['total'] += 1

        traffic_class = get_traffic_class(pkt)
        packet_size = len(pkt)

        bucket = buckets.get(traffic_class, buckets['data'])

        if bucket.consume(packet_size):
            # Packet within rate limit - FORWARD
            sendp(pkt, iface='eth0', verbose=False)
            stats['passed'] += 1
            stats[f'{traffic_class}_passed'] += 1
        else:
            # Packet exceeds rate limit - DROP
            stats['dropped'] += 1
            stats[f'{traffic_class}_dropped'] += 1

        # Log every 500 packets
        if stats['total'] % 500 == 0:
            drop_rate = (stats['dropped'] / stats['total']) * 100
            logger.info(
                f"Stats: Total={stats['total']} | "
                f"Passed={stats['passed']} | Dropped={stats['dropped']} ({drop_rate:.1f}%) | "
                f"VoIP: {stats['voip_passed']}/{stats['voip_dropped']} | "
                f"Video: {stats['video_passed']}/{stats['video_dropped']} | "
                f"Data: {stats['data_passed']}/{stats['data_dropped']}")

    except Exception as e:
        if stats['total'] % 100 == 1:  # Log only occasionally
            logger.error(f"Error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("Policing VNF Started")
    logger.info("=" * 60)
    logger.info(f"Next hop: {NEXT_HOP}")
    logger.info("Rate Limits:")
    logger.info("  - VoIP:  1 Mbps (125 KB/s)")
    logger.info("  - Video: 10 Mbps (1250 KB/s)")
    logger.info("  - Data:  5 Mbps (625 KB/s)")
    logger.info("=" * 60)

    try:
        sniff(iface='eth0', prn=police_and_forward, store=0, promisc=True)
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Policing VNF Stopped")
        logger.info(f"Final Statistics: {stats}")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()