from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP
import logging
import sys
import os

logging.basicConfig(
    level=logging.DEBUG,
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
            logger.debug("❌ Packet without IP layer")
            return DSCP_BE, 'unknown'

        ip_layer = pkt[IP]

        # Log every packet details (for debugging and it looks cool)
        logger.debug(f"📦 Packet #{stats['total']}: {ip_layer.src} -> {ip_layer.dst} | Proto: {ip_layer.proto}")

        # Check UDP (VoIP)
        if pkt.haslayer(UDP):
            udp = pkt[UDP]
            logger.info(f"🔊 UDP Packet: {udp.sport} -> {udp.dport}")
            if udp.dport == 5004 or udp.sport == 5004:
                logger.info("🎯 *** VOIP TRAFFIC CLASSIFIED ***")
                return DSCP_EF, 'voip'

        # Check TCP
        if pkt.haslayer(TCP):
            tcp = pkt[TCP]
            logger.info(f"📹 TCP Packet: {tcp.sport} -> {tcp.dport}")
            # Video
            if tcp.dport == 8080 or tcp.sport == 8080:
                logger.info("🎯 *** VIDEO TRAFFIC CLASSIFIED ***")
                return DSCP_AF41, 'video'
            # Data
            elif tcp.dport == 5001 or tcp.sport == 5001:
                logger.info("🎯 *** DATA TRAFFIC CLASSIFIED ***")
                return DSCP_BE, 'data'

        # Fallback: Classify by source IP
        if ip_layer.src == '10.0.0.11':  # client_video
            logger.info("🔄 Fallback: Video by IP")
            return DSCP_AF41, 'video'
        elif ip_layer.src == '10.0.0.12':  # client_data
            logger.info("🔄 Fallback: Data by IP")
            return DSCP_BE, 'data'
        elif ip_layer.src == '10.0.0.10':  # client_voip
            logger.info("🔄 Fallback: VoIP by IP")
            return DSCP_EF, 'voip'

        logger.debug("❓ Could not classify packet")
        return DSCP_BE, 'unknown'

    except Exception as e:
        logger.error(f"💥 Classification error: {e}")
        return DSCP_BE, 'unknown'


def mark_and_forward(pkt):
    try:
        stats['total'] += 1

        if stats['total'] <= 20 or stats['total'] % 50 == 0:
            logger.info(f"🔍 Packet #{stats['total']} - Layers: {pkt.summary()}")

            if pkt.haslayer(IP):
                ip_src = pkt[IP].src
                ip_dst = pkt[IP].dst
                proto = pkt[IP].proto
                logger.info(f"   📦 IP: {ip_src} -> {ip_dst} (proto: {proto})")

                if pkt.haslayer(TCP):
                    tcp = pkt[TCP]
                    logger.info(f"   📹 TCP: {tcp.sport} -> {tcp.dport}")
                elif pkt.haslayer(UDP):
                    udp = pkt[UDP]
                    logger.info(f"   🔊 UDP: {udp.sport} -> {udp.dport}")
            else:
                logger.info(f"   🚫 Non-IP packet: {pkt.summary()}")

        if not pkt.haslayer(IP):
            logger.debug("❌ Skipping non-IP packet")
            return
        dscp, traffic_type = classify_packet(pkt)

        if traffic_type in stats:
            stats[traffic_type] += 1
        else:
            stats['unknown'] += 1

        # Mark DSCP in IP header
        if pkt.haslayer(IP):
            original_tos = pkt[IP].tos
            pkt[IP].tos = dscp << 2
            if original_tos != pkt[IP].tos:
                logger.debug(f"🏷️ DSCP marked: {original_tos} -> {pkt[IP].tos} for {traffic_type}")

        sendp(pkt, iface='eth0', verbose=False)
        stats['forwarded'] += 1

        if stats['total'] % 50 == 0:
            logger.info(
                f"📊 Progress: Total={stats['total']} | "
                f"VoIP={stats['voip']} | Video={stats['video']} | "
                f"Data={stats['data']} | Unknown={stats['unknown']}")

    except Exception as e:
        stats['errors'] += 1
        logger.error(f"💥 Forward error: {e}")


def main():
    logger.info("🚀" * 20)
    logger.info("🚀 Classification VNF Started - ULTRA DEBUG MODE")
    logger.info("🚀" * 20)
    logger.info(f"📍 Next hop: {NEXT_HOP}")
    logger.info("👂 Listening for traffic on eth0...")

    try:
        sniff(iface='eth0', prn=mark_and_forward, store=0, promisc=True)
    except KeyboardInterrupt:
        logger.info("\n" + "🛑" * 20)
        logger.info("🛑 Classification VNF Stopped")
        logger.info(f"📈 Final Statistics: {stats}")
        logger.info("🛑" * 20)
    except Exception as e:
        logger.error(f"💀 Fatal error: {e}")


if __name__ == "__main__":
    main()