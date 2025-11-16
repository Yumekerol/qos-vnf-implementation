from scapy.all import *
import logging
import sys
import os
import time
from threading import Lock

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/policing.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Policing-VNF')

NEXT_HOP = os.environ.get('NEXT_HOP', '10.0.0.22')


class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = Lock()

    def consume(self, tokens_needed):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if tokens_needed <= self.tokens:
                self.tokens -= tokens_needed
                return True
            return False


buckets = {
    'voip': TokenBucket(rate=125000, capacity=250000),  # 1 Mbps
    'video': TokenBucket(rate=1250000, capacity=2500000),  # 10 Mbps
    'data': TokenBucket(rate=625000, capacity=1250000),  # 5 Mbps
}

stats = {'total': 0, 'passed': 0, 'dropped': 0}


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
    return 'data'


def police_and_forward(pkt):
    try:
        stats['total'] += 1

        traffic_class = get_traffic_class(pkt)
        packet_size = len(pkt)

        bucket = buckets.get(traffic_class)
        if bucket and bucket.consume(packet_size):
            # Forward packet
            send(pkt, verbose=False)
            stats['passed'] += 1
        else:
            # Drop packet
            stats['dropped'] += 1

        # Log every 1000 packets
        if stats['total'] % 1000 == 0:
            drop_rate = (stats['dropped'] / stats['total']) * 100
            logger.info(
                f"Processed {stats['total']} | Passed: {stats['passed']} | Dropped: {stats['dropped']} ({drop_rate:.1f}%)")

    except Exception as e:
        logger.error(f"Error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("Policing VNF started (FORWARDING MODE)")
    logger.info("=" * 60)
    logger.info(f"Next hop: {NEXT_HOP}")
    logger.info("Rate limits: VoIP=1Mbps | Video=10Mbps | Data=5Mbps")
    logger.info("=" * 60)

    try:
        sniff(iface='eth0', prn=police_and_forward, store=0)
    except KeyboardInterrupt:
        logger.info(f"\nFinal stats: {stats}")


if __name__ == "__main__":
    main()