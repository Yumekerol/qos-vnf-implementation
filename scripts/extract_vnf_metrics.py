#!/usr/bin/env python3
"""Extract VNF metrics from logs"""

import subprocess
import re
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd):
    """Execute command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout
    except:
        return ""


def extract_number(text, pattern):
    """Extract number from text using regex"""
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0


def main():
    print("=" * 60)
    print("VNF Metrics Extraction")
    print("=" * 60)
    print()

    # Check if containers are running
    ps_output = run_command("docker ps")
    if "vnf_classification" not in ps_output:
        print("Error: VNF containers not running")
        print("Start them with: docker-compose up -d")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Create output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(f"./vnf_metrics_{timestamp}.txt")

    report_lines = []
    report_lines.append("VNF METRICS REPORT")
    report_lines.append(f"Generated: {datetime.now()}")
    report_lines.append("=" * 60)
    report_lines.append("")

    # ===== CLASSIFICATION VNF =====
    report_lines.append("=== CLASSIFICATION VNF ===")
    report_lines.append("")

    class_log = run_command("docker exec vnf_classification cat /logs/classification.log")

    if class_log:
        # Find last stats line
        stats_lines = [line for line in class_log.split('\n') if 'Total=' in line]
        if stats_lines:
            last_stats = stats_lines[-1]

            total = extract_number(last_stats, r'Total=(\d+)')
            voip = extract_number(last_stats, r'VoIP=(\d+)')
            video = extract_number(last_stats, r'Video=(\d+)')
            data = extract_number(last_stats, r'Data=(\d+)')
            unknown = extract_number(last_stats, r'Unknown=(\d+)')

            report_lines.append(f"Total packets processed: {total}")
            report_lines.append("")
            report_lines.append("Traffic breakdown:")
            report_lines.append(f"  VoIP:    {voip} packets")
            report_lines.append(f"  Video:   {video} packets")
            report_lines.append(f"  Data:    {data} packets")
            report_lines.append(f"  Unknown: {unknown} packets")
            report_lines.append("")

            if total > 0:
                voip_pct = (voip / total) * 100
                video_pct = (video / total) * 100
                data_pct = (data / total) * 100

                report_lines.append("Traffic distribution:")
                report_lines.append(f"  VoIP:  {voip_pct:.2f}%")
                report_lines.append(f"  Video: {video_pct:.2f}%")
                report_lines.append(f"  Data:  {data_pct:.2f}%")

        report_lines.append("")
        report_lines.append("Classification events:")
        voip_class = class_log.count("VOIP TRAFFIC CLASSIFIED")
        video_class = class_log.count("VIDEO TRAFFIC CLASSIFIED")
        data_class = class_log.count("DATA TRAFFIC CLASSIFIED")

        report_lines.append(f"  VoIP classifications: {voip_class}")
        report_lines.append(f"  Video classifications: {video_class}")
        report_lines.append(f"  Data classifications: {data_class}")
    else:
        report_lines.append("No logs found in Classification VNF")

    report_lines.append("")
    report_lines.append("")

    # ===== POLICING VNF =====
    report_lines.append("=== POLICING VNF ===")
    report_lines.append("")

    police_log = run_command("docker exec vnf_policing cat /logs/policing.log")

    if police_log:
        # Find last stats line
        stats_lines = [line for line in police_log.split('\n') if 'Stats: Total=' in line]
        if stats_lines:
            last_stats = stats_lines[-1]

            p_total = extract_number(last_stats, r'Total=(\d+)')

            # Extract VoIP stats (format: VoIP: passed/dropped)
            voip_match = re.search(r'VoIP: (\d+)/(\d+)', last_stats)
            voip_passed = int(voip_match.group(1)) if voip_match else 0
            voip_dropped = int(voip_match.group(2)) if voip_match else 0

            video_match = re.search(r'Video: (\d+)/(\d+)', last_stats)
            video_passed = int(video_match.group(1)) if video_match else 0
            video_dropped = int(video_match.group(2)) if video_match else 0

            data_match = re.search(r'Data: (\d+)/(\d+)', last_stats)
            data_passed = int(data_match.group(1)) if data_match else 0
            data_dropped = int(data_match.group(2)) if data_match else 0

            report_lines.append(f"Total packets processed: {p_total}")
            report_lines.append("")

            # VoIP stats
            report_lines.append("VoIP (1 Mbps limit):")
            report_lines.append(f"  Passed:  {voip_passed}")
            report_lines.append(f"  Dropped: {voip_dropped}")
            if voip_passed + voip_dropped > 0:
                drop_rate = (voip_dropped / (voip_passed + voip_dropped)) * 100
                report_lines.append(f"  Drop rate: {drop_rate:.2f}%")

            report_lines.append("")

            # Video stats
            report_lines.append("Video (10 Mbps limit):")
            report_lines.append(f"  Passed:  {video_passed}")
            report_lines.append(f"  Dropped: {video_dropped}")
            if video_passed + video_dropped > 0:
                drop_rate = (video_dropped / (video_passed + video_dropped)) * 100
                report_lines.append(f"  Drop rate: {drop_rate:.2f}%")

            report_lines.append("")

            # Data stats
            report_lines.append("Data (5 Mbps limit):")
            report_lines.append(f"  Passed:  {data_passed}")
            report_lines.append(f"  Dropped: {data_dropped}")
            if data_passed + data_dropped > 0:
                drop_rate = (data_dropped / (data_passed + data_dropped)) * 100
                report_lines.append(f"  Drop rate: {drop_rate:.2f}%")
        else:
            report_lines.append("No statistics found in policing logs")

        report_lines.append("")
        report_lines.append("Drop events:")
        voip_drops = police_log.count("Dropped voip packet")
        video_drops = police_log.count("Dropped video packet")
        data_drops = police_log.count("Dropped data packet")

        report_lines.append(f"  VoIP drops: {voip_drops}")
        report_lines.append(f"  Video drops: {video_drops}")
        report_lines.append(f"  Data drops: {data_drops}")
    else:
        report_lines.append("No logs found in Policing VNF")

    report_lines.append("")
    report_lines.append("")

    # ===== MONITORING VNF =====
    report_lines.append("=== MONITORING VNF ===")
    report_lines.append("")

    mon_log = run_command("docker exec vnf_monitoring cat /logs/monitoring.log")

    if mon_log:
        # Find last stats
        stats_lines = [line for line in mon_log.split('\n') if 'Total Packets:' in line]
        if stats_lines:
            last_line = stats_lines[-1]

            m_total = extract_number(last_line.replace(',', ''), r'Total Packets: (\d+)')
            m_bytes = extract_number(last_line.replace(',', ''), r'Bytes: (\d+)')

            report_lines.append(f"Total packets monitored: {m_total:,}")
            report_lines.append(f"Total bytes: {m_bytes:,}")

            # Find throughput
            throughput_lines = [line for line in mon_log.split('\n') if 'Throughput:' in line]
            if throughput_lines:
                last_tp = throughput_lines[-1]
                tp_match = re.search(r'Throughput: ([\d.]+)', last_tp)
                if tp_match:
                    report_lines.append(f"Throughput: {tp_match.group(1)} Mbps")

            report_lines.append("")
            report_lines.append("Traffic class breakdown:")

            # Find traffic breakdown
            breakdown_start = mon_log.rfind("Traffic Breakdown:")
            if breakdown_start != -1:
                breakdown_section = mon_log[breakdown_start:breakdown_start + 500]
                for line in breakdown_section.split('\n')[1:6]:
                    if any(word in line for word in ["VOIP", "VIDEO", "DATA", "OTHER"]):
                        report_lines.append(f"  {line.strip()}")
        else:
            report_lines.append("No statistics found in monitoring logs")
    else:
        report_lines.append("No logs found in Monitoring VNF")

    report_lines.append("")
    report_lines.append("")
    report_lines.append("=" * 60)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 60)

    # Print and save report
    report_text = '\n'.join(report_lines)
    print(report_text)

    with open(output_file, 'w') as f:
        f.write(report_text)

    print(f"\n\nReport saved to: {output_file}")

    print("\n" + "=" * 60)
    print("QUICK SUMMARY")
    print("=" * 60)

    if class_log and 'total' in locals():
        print(f"\nClassification: {total} packets processed")
        print(f"  ├─ VoIP:  {voip} ({voip_pct:.1f}%)")
        print(f"  ├─ Video: {video} ({video_pct:.1f}%)")
        print(f"  └─ Data:  {data} ({data_pct:.1f}%)")

    if police_log and stats_lines:
        print("\nPolicing: Rate limiting active")
        total_drops = voip_dropped + video_dropped + data_dropped
        if total_drops > 0:
            print("  ⚠️  Drops detected - rate limits enforced")
            if voip_dropped > 0:
                print(f"    - VoIP: {voip_dropped} dropped")
            if video_dropped > 0:
                print(f"    - Video: {video_dropped} dropped")
            if data_dropped > 0:
                print(f"    - Data: {data_dropped} dropped")
        else:
            print("  ✓ No drops - traffic within limits")

    if mon_log and stats_lines:
        print(f"\nMonitoring: {m_total:,} packets observed")
        if throughput_lines:
            print(f"  └─ Throughput: {tp_match.group(1)} Mbps")

    print("\n" + "=" * 60)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)