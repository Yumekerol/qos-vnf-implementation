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

            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if tokens_needed <= self.tokens:
                self.tokens -= tokens_needed
                return True
            return False

buckets = {
    'voip': TokenBucket(
        rate=25000,      # 0.2 Mbps = 25 KB/s (margem de 33% sobre 150Kbps)
        capacity=50000   # Burst de 50 KB (permite jitter)
    ),
    'video': TokenBucket(
        rate=500000,     # 4 Mbps = 500 KB/s (margem sobre 3Mbps)
        capacity=1000000
    ),
    'data': TokenBucket(
        rate=250000,     # 2 Mbps = 250 KB/s (best-effort)
        capacity=500000  # Burst de 500 KB
    ),
    'other': TokenBucket(
        rate=125000,     # 1 Mbps = 125 KB/s
        capacity=250000
    )
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
            if dscp == 46:  # EF
                return 'voip'
            elif dscp == 34:  # AF41
                return 'video'
            elif dscp == 0:  # BE
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

        # Apply policing with priority for VoIP
        if traffic_class == 'voip':
            # VoIP SEMPRE tem prioridade - nunca dropar se estiver na taxa
            if bucket.consume(packet_size):
                stats['voip_passed'] += 1
                packet.accept()
            else:
                # Log mais agressivo para VoIP drops (NÃO DEVERIA ACONTECER!)
                stats['voip_dropped'] += 1
                logger.error(f"! CRITICAL: VoIP packet DROPPED! Size={packet_size} bytes")
                packet.drop()
        else:
            # Video e Data: policing normal
            if bucket.consume(packet_size):
                stats[f'{traffic_class}_passed'] += 1
                packet.accept()
            else:
                stats[f'{traffic_class}_dropped'] += 1
                packet.drop()
                if stats['total'] % 500 == 0:  # Log menos frequente
                    logger.warning(f"Dropped {traffic_class} packet (Rate limit exceeded)")

        # Log statistics occasionally
        if stats['total'] % 1000 == 0:  # A cada 1000 pacotes
            logger.info(
                f"Stats: Total={stats['total']} | "
                f"VoIP: {stats['voip_passed']}/{stats['voip_dropped']} "
                f"({100*stats['voip_passed']/(stats['voip_passed']+stats['voip_dropped']+0.001):.1f}% pass) | "
                f"Video: {stats['video_passed']}/{stats['video_dropped']} | "
                f"Data: {stats['data_passed']}/{stats['data_dropped']}"
            )

    except Exception as e:
        logger.error(f"Error processing packet: {e}")
        packet.accept()  # Default to accept on error


def main():
    logger.info("=" * 60)
    logger.info("Policing VNF Started - OPTIMIZED CONFIG")
    logger.info("=" * 60)
    logger.info(f"Next hop: {NEXT_HOP}")
    logger.info("Rate Limits (Optimized for Real Traffic):")
    logger.info("  - VoIP:  0.2 Mbps (25 KB/s) - STRICT PROTECTION")
    logger.info("  - Video: 4 Mbps (500 KB/s) - MEDIUM PRIORITY")
    logger.info("  - Data:  2 Mbps (250 KB/s) - BEST EFFORT")
    logger.info("=" * 60)
    logger.warning("!  VoIP drops should be ZERO in all scenarios!")
    logger.info("=" * 60)

    nfqueue = NetfilterQueue()
    nfqueue.bind(0, process_packet, max_len=10000)

    try:
        nfqueue.run()
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Policing VNF Stopped")
        logger.info(f"Final Statistics:")
        logger.info(f"  VoIP:  {stats['voip_passed']} passed / {stats['voip_dropped']} dropped")
        logger.info(f"  Video: {stats['video_passed']} passed / {stats['video_dropped']} dropped")
        logger.info(f"  Data:  {stats['data_passed']} passed / {stats['data_dropped']} dropped")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        nfqueue.unbind()


if __name__ == "__main__":
    main()