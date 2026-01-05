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
            print(f"    [OK] Loaded: {filepath.name}")
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


def plot_throughput_comparison(with_policing, without_policing, output_dir):
    categories = ['VoIP', 'Video', 'Data']

    with_values = [
        with_policing['voip']['throughput'],
        with_policing['video']['throughput'],
        with_policing['data']['throughput']
    ]

    without_values = [
        without_policing['voip']['throughput'],
        without_policing['video']['throughput'],
        without_policing['data']['throughput']
    ]

    x = np.arange(len(categories))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 7))

    # Darker colors for 'without' to match the original style, plus hatching
    colors_with = ['#2ecc71', '#3498db', '#e74c3c']
    colors_without = ['#27ae60', '#2980b9', '#c0392b']

    bars1 = ax.bar(x - width / 2, with_values, width, label='With Policing',
                   color=colors_with, alpha=0.9, edgecolor='black')
    bars2 = ax.bar(x + width / 2, without_values, width, label='Without Policing',
                   color=colors_without, alpha=0.9, edgecolor='black', hatch='//')

    ax.set_xlabel('Traffic Type', fontsize=13, fontweight='bold')
    ax.set_ylabel('Throughput (Mbps)', fontsize=13, fontweight='bold')
    ax.set_title('Throughput Comparison: With vs Without Policing VNF',
                 fontsize=15, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=12)
    
    # Custom Legend
    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(facecolor='#2ecc71', edgecolor='black', label='VoIP (With Policing)'),
        mpatches.Patch(facecolor='#27ae60', edgecolor='black', hatch='//', label='VoIP (Without Policing)'),
        mpatches.Patch(facecolor='#3498db', edgecolor='black', label='Video (With Policing)'),
        mpatches.Patch(facecolor='#2980b9', edgecolor='black', hatch='//', label='Video (Without Policing)'),
        mpatches.Patch(facecolor='#e74c3c', edgecolor='black', label='Data (With Policing)'),
        mpatches.Patch(facecolor='#c0392b', edgecolor='black', hatch='//', label='Data (Without Policing)')
    ]
    ax.legend(handles=legend_handles, fontsize=10, loc='upper right', ncol=2)
    
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    forbars = [bars1, bars2]
    for bars in forbars:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                    f'{height:.2f}',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_dir / 'comparison_throughput.png', dpi=300, bbox_inches='tight')
    print(f"[OK] Saved: comparison_throughput.png")
    plt.close()


def plot_voip_quality_comparison(with_policing, without_policing, output_dir):

    with_values = [
        with_policing['voip']['jitter'],
        with_policing['voip']['loss']
    ]

    without_values = [
        without_policing['voip']['jitter'],
        without_policing['voip']['loss']
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    x1 = np.arange(2)
    width = 0.35

    ax1.bar(x1 - width / 2, [with_values[0], 0], width,
            label='With Policing', color='#2ecc71', edgecolor='black')
    ax1.bar(x1 + width / 2, [without_values[0], 0], width,
            label='Without Policing', color='#27ae60', edgecolor='black')

    ax1.axhline(y=30, color='red', linestyle='--', linewidth=2,
                label='Acceptable limit (30ms)')
    ax1.set_ylabel('Jitter (ms)', fontsize=12, fontweight='bold')
    ax1.set_title('VoIP Jitter Comparison', fontsize=13, fontweight='bold')
    ax1.set_xticks([0])
    ax1.set_xticklabels(['VoIP'])
    ax1.legend(fontsize=10)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.set_ylim(0, max(with_values[0], without_values[0], 35) * 1.2)

    for i, v in enumerate([with_values[0], without_values[0]]):
        ax1.text(x1[0] + (i - 0.5) * width, v, f'{v:.2f}',
                 ha='center', va='bottom', fontweight='bold')

    ax2.bar(x1 - width / 2, [with_values[1], 0], width,
            label='With Policing', color='#e74c3c', edgecolor='black')
    ax2.bar(x1 + width / 2, [without_values[1], 0], width,
            label='Without Policing', color='#c0392b', edgecolor='black')

    ax2.axhline(y=1, color='red', linestyle='--', linewidth=2,
                label='Acceptable limit (1%)')
    ax2.set_ylabel('Packet Loss (%)', fontsize=12, fontweight='bold')
    ax2.set_title('VoIP Packet Loss Comparison', fontsize=13, fontweight='bold')
    ax2.set_xticks([0])
    ax2.set_xticklabels(['VoIP'])
    ax2.legend(fontsize=10)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.set_ylim(0, max(with_values[1], without_values[1], 2) * 1.2)

    for i, v in enumerate([with_values[1], without_values[1]]):
        ax2.text(x1[0] + (i - 0.5) * width, v, f'{v:.2f}',
                 ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_dir / 'comparison_voip_quality.png', dpi=300, bbox_inches='tight')
    print(f"[OK] Saved: comparison_voip_quality.png")
    plt.close()


def plot_retransmissions_comparison(with_policing, without_policing, output_dir):
    categories = ['Video', 'Data']

    with_values = [
        with_policing['video']['retransmits'],
        with_policing['data']['retransmits']
    ]

    without_values = [
        without_policing['video']['retransmits'],
        without_policing['data']['retransmits']
    ]

    x = np.arange(len(categories))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 7))

    colors_with = ['#3498db', '#e74c3c']
    colors_without = ['#2980b9', '#c0392b']

    bars1 = ax.bar(x - width / 2, with_values, width, label='With Policing',
                   color=colors_with, alpha=0.9, edgecolor='black')
    bars2 = ax.bar(x + width / 2, without_values, width, label='Without Policing',
                   color=colors_without, alpha=0.9, edgecolor='black', hatch='//')

    ax.set_xlabel('Traffic Type', fontsize=13, fontweight='bold')
    ax.set_ylabel('Retransmissions', fontsize=13, fontweight='bold')
    ax.set_title('TCP Retransmissions: With vs Without Policing',
                 fontsize=15, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=12)
    
    # Custom Legend
    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(facecolor='#3498db', edgecolor='black', label='Video (With Policing)'),
        mpatches.Patch(facecolor='#2980b9', edgecolor='black', hatch='//', label='Video (Without Policing)'),
        mpatches.Patch(facecolor='#e74c3c', edgecolor='black', label='Data (With Policing)'),
        mpatches.Patch(facecolor='#c0392b', edgecolor='black', hatch='//', label='Data (Without Policing)')
    ]
    ax.legend(handles=legend_handles, fontsize=10)
    
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_dir / 'comparison_retransmissions.png', dpi=300, bbox_inches='tight')
    print(f"[OK] Saved: comparison_retransmissions.png")
    plt.close()


def plot_fairness_analysis(with_policing, without_policing, output_dir):
    with_total = (with_policing['voip']['throughput'] +
                  with_policing['video']['throughput'] +
                  with_policing['data']['throughput'])

    without_total = (without_policing['voip']['throughput'] +
                     without_policing['video']['throughput'] +
                     without_policing['data']['throughput'])

    with_percentages = [
        (with_policing['voip']['throughput'] / with_total * 100) if with_total > 0 else 0,
        (with_policing['video']['throughput'] / with_total * 100) if with_total > 0 else 0,
        (with_policing['data']['throughput'] / with_total * 100) if with_total > 0 else 0
    ]

    without_percentages = [
        (without_policing['voip']['throughput'] / without_total * 100) if without_total > 0 else 0,
        (without_policing['video']['throughput'] / without_total * 100) if without_total > 0 else 0,
        (without_policing['data']['throughput'] / without_total * 100) if without_total > 0 else 0
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    colors = ['#2ecc71', '#3498db', '#e74c3c']
    labels = ['VoIP', 'Video', 'Data']

    # With Policing
    wedges1, texts1, autotexts1 = ax1.pie(with_percentages, labels=labels, colors=colors,
                                          autopct='%1.1f%%', startangle=90,
                                          textprops={'fontsize': 11, 'fontweight': 'bold'})
    ax1.set_title('Bandwidth Distribution\nWith Policing',
                  fontsize=13, fontweight='bold', pad=15)

    # Without Policing
    wedges2, texts2, autotexts2 = ax2.pie(without_percentages, labels=labels, colors=colors,
                                          autopct='%1.1f%%', startangle=90,
                                          textprops={'fontsize': 11, 'fontweight': 'bold'})
    ax2.set_title('Bandwidth Distribution\nWithout Policing',
                  fontsize=13, fontweight='bold', pad=15)

    plt.tight_layout()
    plt.savefig(output_dir / 'comparison_fairness.png', dpi=300, bbox_inches='tight')
    print(f"[OK] Saved: comparison_fairness.png")
    plt.close()


def generate_comparison_report(with_policing, without_policing, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# QoS Policing VNF Effectiveness Analysis\n\n")
        f.write("## Comparison: With vs Without Policing\n\n")

        f.write("### VoIP Performance (UDP 150Kbps)\n\n")
        f.write("| Metric | With Policing | Without Policing | Change |\n")
        f.write("|--------|---------------|------------------|--------|\n")

        voip_tp_change = ((without_policing['voip']['throughput'] - with_policing['voip']['throughput']) /
                          with_policing['voip']['throughput'] * 100) if with_policing['voip']['throughput'] > 0 else 0
        voip_jitter_change = ((with_policing['voip']['jitter'] - without_policing['voip']['jitter']) /
                              without_policing['voip']['jitter'] * 100) if with_policing['voip']['jitter'] > 0 else 0
        voip_loss_change = without_policing['voip']['loss'] - with_policing['voip']['loss']

        f.write(f"| Throughput (Mbps) | {with_policing['voip']['throughput']:.3f} | "
                f"{without_policing['voip']['throughput']:.3f} | {voip_tp_change:+.1f}% |\n")
        f.write(f"| Jitter (ms) | {with_policing['voip']['jitter']:.2f} | "
                f"{without_policing['voip']['jitter']:.2f} | {voip_jitter_change:+.1f}% |\n")
        f.write(f"| Packet Loss (%) | {with_policing['voip']['loss']:.2f} | "
                f"{without_policing['voip']['loss']:.2f} | {voip_loss_change:+.2f}pp |\n")

        f.write("\n### Video Performance (TCP 3Mbps target)\n\n")
        f.write("| Metric | With Policing | Without Policing | Change |\n")
        f.write("|--------|---------------|------------------|--------|\n")

        video_tp_change = ((without_policing['video']['throughput'] - with_policing['video']['throughput']) /
                           with_policing['video']['throughput'] * 100) if with_policing['video'][
                                                                              'throughput'] > 0 else 0
        video_retrans_change = without_policing['video']['retransmits'] - with_policing['video']['retransmits']

        f.write(f"| Throughput (Mbps) | {with_policing['video']['throughput']:.2f} | "
                f"{without_policing['video']['throughput']:.2f} | {video_tp_change:+.1f}% |\n")
        f.write(f"| Retransmissions | {with_policing['video']['retransmits']} | "
                f"{without_policing['video']['retransmits']} | {video_retrans_change:+d} |\n")

        f.write("\n### Data Performance (TCP Best Effort)\n\n")
        f.write("| Metric | With Policing | Without Policing | Change |\n")
        f.write("|--------|---------------|------------------|--------|\n")

        data_tp_change = ((without_policing['data']['throughput'] - with_policing['data']['throughput']) /
                          with_policing['data']['throughput'] * 100) if with_policing['data']['throughput'] > 0 else 0
        data_retrans_change = without_policing['data']['retransmits'] - with_policing['data']['retransmits']

        f.write(f"| Throughput (Mbps) | {with_policing['data']['throughput']:.2f} | "
                f"{without_policing['data']['throughput']:.2f} | {data_tp_change:+.1f}% |\n")
        f.write(f"| Retransmissions | {with_policing['data']['retransmits']} | "
                f"{without_policing['data']['retransmits']} | {data_retrans_change:+d} |\n")

        f.write("\n## Key Findings\n\n")
        f.write("### Impact of Policing VNF\n\n")

        if abs(voip_loss_change) < 0.5:
            f.write(
                "- **VoIP Protection**: Policing maintains excellent VoIP quality with minimal packet loss in both scenarios.\n")
        elif voip_loss_change < 0:
            f.write(
                f"- **VoIP Protection**: Policing reduces packet loss by {abs(voip_loss_change):.2f} percentage points, "
                "demonstrating effective priority enforcement.\n")
        else:
            f.write(
                f"- **VoIP Protection**: Without policing, VoIP packet loss increases by {voip_loss_change:.2f} percentage points.\n")

        total_with = (with_policing['voip']['throughput'] + with_policing['video']['throughput'] +
                      with_policing['data']['throughput'])
        total_without = (without_policing['voip']['throughput'] + without_policing['video']['throughput'] +
                         without_policing['data']['throughput'])

        f.write(f"- **Total Throughput**: With policing: {total_with:.2f} Mbps | "
                f"Without policing: {total_without:.2f} Mbps\n")

        if abs(data_tp_change) > 10:
            f.write(
                f"- **Traffic Fairness**: Data traffic throughput changes by {data_tp_change:+.1f}% without policing, "
                "indicating policing's role in bandwidth allocation control.\n")

        f.write("\n### Conclusions\n\n")
        f.write("1. The Policing VNF enforces configured rate limits, ensuring priority traffic (VoIP) "
                "receives guaranteed bandwidth.\n")
        f.write("2. Without policing, traffic competes based on TCP congestion control, which may not "
                "respect application priorities.\n")
        f.write("3. Policing introduces controlled degradation for lower-priority traffic while "
                "protecting high-priority flows.\n")

    print(f"[OK] Saved: comparison_report.md")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_policing_comparison.py <results_directory>")
        print("\nExample:")
        print("  python analyze_policing_comparison.py ./test_results/policing_comparison_20250119_143022")
        sys.exit(1)

    results_dir = Path(sys.argv[1])

    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        sys.exit(1)

    print("=" * 60)
    print("QoS Policing VNF Effectiveness Analysis")
    print("=" * 60)
    print(f"\nAnalyzing: {results_dir}\n")

    with_policing_dir = None
    without_policing_dir = None

    for scenario_dir in sorted(results_dir.iterdir()):
        if scenario_dir.is_dir():
            if 'with_policing' in scenario_dir.name:
                with_policing_dir = scenario_dir
            elif 'without_policing' in scenario_dir.name:
                without_policing_dir = scenario_dir

    if not with_policing_dir or not without_policing_dir:
        print("Error: Could not find both required scenarios!")
        print("Expected directories:")
        print("  - scenario1_baseline_with_policing")
        print("  - scenario2_baseline_without_policing")
        sys.exit(1)

    print("=" * 60)
    with_policing = analyze_scenario(with_policing_dir)
    print("=" * 60)
    without_policing = analyze_scenario(without_policing_dir)
    print("=" * 60)

    print("\nGenerating comparison graphs...")
    try:
        plot_throughput_comparison(with_policing, without_policing, results_dir)
        plot_voip_quality_comparison(with_policing, without_policing, results_dir)
        plot_retransmissions_comparison(with_policing, without_policing, results_dir)
        plot_fairness_analysis(with_policing, without_policing, results_dir)
    except Exception as e:
        print(f"Error generating graphs: {e}")
        import traceback
        traceback.print_exc()

    print("\nGenerating comparison report...")
    try:
        generate_comparison_report(with_policing, without_policing, results_dir / "comparison_report.md")
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Analysis Complete!")
    print("=" * 60)
    print(f"\nGenerated files in {results_dir}:")
    print("  - comparison_throughput.png")
    print("  - comparison_voip_quality.png")
    print("  - comparison_retransmissions.png")
    print("  - comparison_fairness.png")
    print("  - comparison_report.md")
    print("\nNext steps:")
    print("  1. Review graphs to understand policing impact")
    print("  2. Read comparison_report.md for detailed analysis")
    print("  3. Include findings in Phase 3 report")


if __name__ == "__main__":
    main()