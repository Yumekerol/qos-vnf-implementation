import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys


def load_iperf_json(filepath):
    if not filepath.exists():
        print(f"Warning: File not found: {filepath}")
        return None

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            print(f"    ✓ Loaded: {filepath.name}")
            return data
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def extract_voip_metrics(data):
    if not data:
        return {'throughput': 0, 'jitter': 0, 'loss': 0}

    end = data.get('end', {}).get('sum', {})
    return {
        'throughput': end.get('bits_per_second', 0) / 1e6,  # Mbps
        'jitter': end.get('jitter_ms', 0),
        'loss': end.get('lost_percent', 0)
    }


def extract_tcp_metrics(data):
    if not data:
        return {'throughput': 0, 'retransmits': 0}

    sum_received = data.get('end', {}).get('sum_received', {})
    if not sum_received:
        sum_received = data.get('end', {}).get('sum', {})

    sum_sent = data.get('end', {}).get('sum_sent', {})

    return {
        'throughput': sum_received.get('bits_per_second', 0) / 1e6,  # Mbps
        'retransmits': sum_sent.get('retransmits', 0)
    }


def analyze_scenario(scenario_path):
    print(f"\nAnalyzing: {scenario_path.name}")
    voip_data = load_iperf_json(scenario_path / "voip.json")
    video_data = load_iperf_json(scenario_path / "video.json")
    data_data = load_iperf_json(scenario_path / "data.json")

    metrics = {
        'voip': extract_voip_metrics(voip_data),
        'video': extract_tcp_metrics(video_data),
        'data': extract_tcp_metrics(data_data)
    }

    print(
        f"  VoIP:  {metrics['voip']['throughput']:.3f} Mbps | Jitter: {metrics['voip']['jitter']:.2f} ms | Loss: {metrics['voip']['loss']:.2f}%")
    print(f"  Video: {metrics['video']['throughput']:.2f} Mbps | Retrans: {metrics['video']['retransmits']}")
    print(f"  Data:  {metrics['data']['throughput']:.2f} Mbps | Retrans: {metrics['data']['retransmits']}")

    return metrics


def plot_throughput_comparison(results, output_dir):
    scenarios = list(results.keys())

    voip_tp = [results[s]['voip']['throughput'] for s in scenarios]
    video_tp = [results[s]['video']['throughput'] for s in scenarios]
    data_tp = [results[s]['data']['throughput'] for s in scenarios]

    x = np.arange(len(scenarios))
    width = 0.25

    fig, ax = plt.subplots(figsize=(14, 7))

    bars1 = ax.bar(x - width, voip_tp, width, label='VoIP', color='#2ecc71')
    bars2 = ax.bar(x, video_tp, width, label='Video', color='#3498db')
    bars3 = ax.bar(x + width, data_tp, width, label='Data', color='#e74c3c')

    ax.set_xlabel('Scenario', fontsize=12, fontweight='bold')
    ax.set_ylabel('Throughput (Mbps)', fontsize=12, fontweight='bold')
    ax.set_title('Throughput Comparison Across Scenarios', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=45, ha='right')
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    plt.savefig(output_dir / 'throughput_comparison.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: throughput_comparison.png")
    plt.close()


def plot_voip_quality(results, output_dir):
    scenarios = list(results.keys())

    jitter = [results[s]['voip']['jitter'] for s in scenarios]
    loss = [results[s]['voip']['loss'] for s in scenarios]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Jitter plot
    ax1.bar(scenarios, jitter, color='#f39c12', edgecolor='black', linewidth=1.2)
    ax1.axhline(y=30, color='red', linestyle='--', linewidth=2, label='Acceptable limit (30ms)')
    ax1.set_ylabel('Jitter (ms)', fontsize=12, fontweight='bold')
    ax1.set_title('VoIP Jitter', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.set_xticklabels(scenarios, rotation=45, ha='right')

    # Loss plot
    ax2.bar(scenarios, loss, color='#e74c3c', edgecolor='black', linewidth=1.2)
    ax2.axhline(y=1, color='red', linestyle='--', linewidth=2, label='Acceptable limit (1%)')
    ax2.set_ylabel('Packet Loss (%)', fontsize=12, fontweight='bold')
    ax2.set_title('VoIP Packet Loss', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.set_xticklabels(scenarios, rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig(output_dir / 'voip_quality.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: voip_quality.png")
    plt.close()


def plot_tcp_retransmissions(results, output_dir):
    scenarios = list(results.keys())

    video_retrans = [results[s]['video']['retransmits'] for s in scenarios]
    data_retrans = [results[s]['data']['retransmits'] for s in scenarios]

    x = np.arange(len(scenarios))
    width = 0.35

    fig, ax = plt.subplots(figsize=(14, 7))

    bars1 = ax.bar(x - width / 2, video_retrans, width, label='Video', color='#3498db', edgecolor='black',
                   linewidth=1.2)
    bars2 = ax.bar(x + width / 2, data_retrans, width, label='Data', color='#e74c3c', edgecolor='black', linewidth=1.2)

    ax.set_xlabel('Scenario', fontsize=12, fontweight='bold')
    ax.set_ylabel('Retransmissions', fontsize=12, fontweight='bold')
    ax.set_title('TCP Retransmissions Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=45, ha='right')
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    plt.savefig(output_dir / 'tcp_retransmissions.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: tcp_retransmissions.png")
    plt.close()


def generate_summary_table(results, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# QoS Test Results Summary\n\n")

        f.write("## VoIP Performance (UDP 150Kbps)\n\n")
        f.write("| Scenario | Throughput (Mbps) | Jitter (ms) | Loss (%) |\n")
        f.write("|----------|-------------------|-------------|----------|\n")
        for scenario, data in results.items():
            voip = data['voip']
            f.write(f"| {scenario} | {voip['throughput']:.3f} | {voip['jitter']:.2f} | {voip['loss']:.2f} |\n")

        f.write("\n## Video Performance (TCP 5Mbps)\n\n")
        f.write("| Scenario | Throughput (Mbps) | Retransmits |\n")
        f.write("|----------|-------------------|-------------|\n")
        for scenario, data in results.items():
            video = data['video']
            f.write(f"| {scenario} | {video['throughput']:.2f} | {video['retransmits']} |\n")

        f.write("\n## Data Performance (TCP Best Effort)\n\n")
        f.write("| Scenario | Throughput (Mbps) | Retransmits |\n")
        f.write("|----------|-------------------|-------------|\n")
        for scenario, data in results.items():
            data_tcp = data['data']
            f.write(f"| {scenario} | {data_tcp['throughput']:.2f} | {data_tcp['retransmits']} |\n")

        f.write("\n## QoS Effectiveness Analysis\n\n")

        # Find baseline scenario
        baseline_key = None
        for key in results.keys():
            if 'baseline' in key.lower() or 'scenario1' in key.lower():
                baseline_key = key
                break

        if baseline_key:
            baseline_voip = results[baseline_key]['voip']['throughput']

            f.write(f"### VoIP Protection Analysis\n\n")
            f.write(f"**Baseline:** {baseline_key}\n\n")
            f.write(f"| Scenario | VoIP Throughput | Protection Rate | Status |\n")
            f.write("|----------|-----------------|-----------------|--------|\n")

            for scenario, data in results.items():
                voip_tp = data['voip']['throughput']
                if baseline_voip > 0:
                    protection = (voip_tp / baseline_voip) * 100
                else:
                    protection = 0

                status = "✅ PASS" if protection >= 80 else "⚠️ DEGRADED" if protection >= 60 else "❌ FAIL"
                f.write(f"| {scenario} | {voip_tp:.3f} Mbps | {protection:.1f}% | {status} |\n")

            f.write("\n### Success Criteria\n\n")
            f.write("- ✅ **PASS**: VoIP maintains ≥80% throughput\n")
            f.write("- ⚠️ **DEGRADED**: VoIP maintains 60-80% throughput\n")
            f.write("- ❌ **FAIL**: VoIP drops below 60% throughput\n")

    print(f"✓ Saved: summary_report.md")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_results.py <results_directory>")
        print("\nExample:")
        print("  python analyze_results.py ./test_results/comprehensive_20250119_143022")
        sys.exit(1)

    results_dir = Path(sys.argv[1])

    if not results_dir.exists():
        print(f"❌ Error: Directory not found: {results_dir}")
        sys.exit(1)

    print("=" * 60)
    print("QoS Test Results Analysis")
    print("=" * 60)
    print(f"\n📁 Analyzing: {results_dir}\n")

    scenarios = {}
    for scenario_dir in sorted(results_dir.iterdir()):
        if scenario_dir.is_dir():
            voip_file = scenario_dir / "voip.json"
            if voip_file.exists():
                scenario_name = scenario_dir.name
                print(f"\n{'=' * 60}")
                scenarios[scenario_name] = analyze_scenario(scenario_dir)

    if not scenarios:
        print("\n❌ Error: No valid scenarios found!")
        print("Expected files: voip.json, video.json, data.json in each scenario directory")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"✓ Found {len(scenarios)} valid scenarios")
    print("=" * 60)

    print("\n📊 Generating graphs...")
    try:
        plot_throughput_comparison(scenarios, results_dir)
        plot_voip_quality(scenarios, results_dir)
        plot_tcp_retransmissions(scenarios, results_dir)
    except Exception as e:
        print(f"❌ Error generating graphs: {e}")
        import traceback
        traceback.print_exc()

    print("\n📝 Generating summary report...")
    try:
        generate_summary_table(scenarios, results_dir / "summary_report.md")
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("✅ Analysis Complete!")
    print("=" * 60)
    print(f"\n📂 Generated files in {results_dir}:")
    print("  - throughput_comparison.png")
    print("  - voip_quality.png")
    print("  - tcp_retransmissions.png")
    print("  - summary_report.md")
    print("\n📋 Next steps:")
    print("  1. Review graphs for QoS effectiveness")
    print("  2. Check if VoIP maintains >80% throughput under stress")
    print("  3. Document findings in Phase 3 report")


if __name__ == "__main__":
    main()