from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP
from netfilterqueue import NetfilterQueue
import logging
import sys
import os

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
    try:
        if not pkt.haslayer(IP):
            logger.debug(f" XXX Packet without IP layer: {pkt.summary()}")
            return DSCP_BE, 'unknown'

        ip_layer = pkt[IP]

        # Check UDP (VoIP)
        if pkt.haslayer(UDP):
            udp = pkt[UDP]

            if udp.dport == 5004 or udp.sport == 5004:
                logger.info(" *** VOIP TRAFFIC CLASSIFIED ***")
                return DSCP_EF, 'voip'

        # Check TCP
        if pkt.haslayer(TCP):
            tcp = pkt[TCP]
            # logger.info(f"📹 TCP Packet: {tcp.sport} -> {tcp.dport}")
            # Video
            if tcp.dport == 8080 or tcp.sport == 8080:
                logger.info(" *** VIDEO TRAFFIC CLASSIFIED ***")
                return DSCP_AF41, 'video'
            # Data
            elif tcp.dport == 5001 or tcp.sport == 5001:
                logger.info(" *** DATA TRAFFIC CLASSIFIED ***")
                return DSCP_BE, 'data'

        # Fallback: Classify by source IP
        if ip_layer.src == '10.0.0.11':  # client_video
            logger.info("@ Fallback: Video by IP")
            return DSCP_AF41, 'video'
        elif ip_layer.src == '10.0.0.12':  # client_data
            logger.info("@ Fallback: Data by IP")
            return DSCP_BE, 'data'
        elif ip_layer.src == '10.0.0.10':  # client_voip
            logger.info("@ Fallback: VoIP by IP")
            return DSCP_EF, 'voip'

        logger.debug("?? Could not classify packet")
        return DSCP_BE, 'unknown'

    except Exception as e:
        logger.error(f"**** Classification error: {e}")
        return DSCP_BE, 'unknown'


def process_packet(packet):
    try:
        stats['total'] += 1

        # Get the packet payload from netfilterqueue
        pkt = IP(packet.get_payload())

        if stats['total'] % 1000 == 0:
            logger.info(f":0 Packet #{stats['total']} - {pkt.summary()}")

        dscp, traffic_type = classify_packet(pkt)

        if traffic_type in stats:
            stats[traffic_type] += 1
        else:
            stats['unknown'] += 1

        # Mark DSCP in IP header
        if pkt.haslayer(IP):
            original_tos = pkt[IP].tos
            new_tos = dscp << 2
            
            if original_tos != new_tos:
                pkt[IP].tos = new_tos
                logger.debug(f"# DSCP marked: {original_tos} -> {new_tos} for {traffic_type}")
                
                # Delete checksums so they get recalculated
                del pkt[IP].chksum
                if pkt.haslayer(TCP):
                    del pkt[TCP].chksum
                elif pkt.haslayer(UDP):
                    del pkt[UDP].chksum
                
                # Set the modified packet back to netfilterqueue
                packet.set_payload(bytes(pkt))
                packet.accept()
                stats['forwarded'] += 1
            else:
                # No change needed, just accept original packet
                packet.accept()
                stats['forwarded'] += 1
        else:
            packet.accept()
            stats['forwarded'] += 1

        if stats['total'] % 1000 == 0:
            logger.info(
                f"# Progress: Total={stats['total']} | "
                f"VoIP={stats['voip']} | Video={stats['video']} | "
                f"Data={stats['data']} | Unknown={stats['unknown']}")

    except Exception as e:
        stats['errors'] += 1
        logger.error(f"*** Process error: {e}")
        packet.accept()  # Accept packet even on error to avoid blocking traffic


def main():
    logger.info("..." * 20)
    logger.info(" Classification VNF Started - NFQUEUE MODE")
    logger.info("..." * 20)
    logger.info(f"! Next hop: {NEXT_HOP}")
    logger.info(":D Listening for traffic on NFQUEUE 0...")

    nfqueue = NetfilterQueue()
    nfqueue.bind(0, process_packet, max_len=10000)

    try:
        nfqueue.run()
    except KeyboardInterrupt:
        logger.info("\n" + "stop" * 20)
        logger.info(" Classification VNF Stopped")
        logger.info(f" Final Statistics: {stats}")
        logger.info("stop" * 20)
    except Exception as e:
        logger.error(f".!!Fatal error: {e}")
    finally:
        nfqueue.unbind()


if __name__ == "__main__":
    main()