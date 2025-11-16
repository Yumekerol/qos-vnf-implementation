from scapy.all import *
import logging
import sys
import os
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/classification.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Classification-VNF')

# DSCP Values
DSCP_EF = 46  # VoIP
DSCP_AF41 = 34  # Video
DSCP_BE = 0  # Data

# Next hop
NEXT_HOP = os.environ.get('NEXT_HOP', '10.0.0.21')

# Statistics
stats = {
    'total': 0,
    'voip': 0,
    'video': 0,
    'data': 0,
    'unknown': 0,
    'forwarded': 0,
    'errors': 0
}


def classify_packet(pkt):
    """Classify packet and return DSCP value"""
    try:
        if not pkt.haslayer(IP):
            return DSCP_BE, 'unknown'

        # Check UDP (VoIP)
        if pkt.haslayer(UDP):
            if pkt[UDP].dport == 5004:
                return DSCP_EF, 'voip'

        # Check TCP
        if pkt.haslayer(TCP):
            dport = pkt[TCP].dport
            if dport == 8080:
                return DSCP_AF41, 'video'
            elif dport == 5001:
                return DSCP_BE, 'data'

        return DSCP_BE, 'unknown'

    except Exception as e:
        logger.error(f"Classification error: {e}")
        return DSCP_BE, 'unknown'


def mark_and_forward(pkt):
    try:
        stats['total'] += 1

        # Classify
        dscp, traffic_type = classify_packet(pkt)

        # Update stats
        if traffic_type in stats:
            stats[traffic_type] += 1

        # Mark DSCP
        if pkt.haslayer(IP):
            pkt[IP].tos = dscp << 2

            # Recalculate checksums
            del pkt[IP].chksum
            if pkt.haslayer(TCP):
                del pkt[TCP].chksum
            elif pkt.haslayer(UDP):
                del pkt[UDP].chksum

        # Forward packet
        send(pkt, verbose=False)
        stats['forwarded'] += 1

        if stats['total'] % 100 == 0:
            logger.info(
                f"Processed {stats['total']} packets | VoIP: {stats['voip']} | Video: {stats['video']} | Data: {stats['data']} | Forwarded: {stats['forwarded']}")

    except Exception as e:
        stats['errors'] += 1
        logger.error(f"Forward error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("Classification VNF started (FORWARDING MODE)")
    logger.info("=" * 60)
    logger.info(f"Next hop: {NEXT_HOP}")
    logger.info("Listening for packets to classify and forward...")
    logger.info("=" * 60)

    try:
        sniff(iface='eth0', prn=mark_and_forward, store=0)
    except KeyboardInterrupt:
        logger.info("\nStopping Classification VNF...")
        logger.info(f"Final stats: {stats}")
    except Exception as e:
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()