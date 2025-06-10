import os
import pandas as pd
import matplotlib.pyplot as plt
import mplhep
import re

mplhep.style.use("CMS")

# Map sequence keys to display labels for scatter plot
SEQUENCE_LABELS = {
    'triton_1server': '1 GPU',
    'triton_2servers': '2 GPUs',
    'triton_3servers': '3 GPUs',
    'triton_4servers': '4 GPUs',
    'triton_5servers': '5',
    'triton_6servers': '6',
    'triton_7servers': '7',
    'triton_8servers': '8',
    'triton_9servers': '9',
    'triton_10servers': '10',
    'supersonic': 'SuperSONIC',
    # Add more mappings as needed
}


def plot_results(run_dir, keys):
    # 1. For each sequence, plot running number of clients and servers vs. time and latency/gpu vs. time
    for key in keys:
        live_metrics_csv = os.path.join(run_dir, f'sonic_benchmark_live_metrics_{key}.csv')
        if not os.path.exists(live_metrics_csv):
            continue
        df_live = pd.read_csv(live_metrics_csv)
        df_live['timestamp'] = pd.to_datetime(df_live['timestamp'])
        # Plot running clients/servers
        plt.figure(figsize=(8, 8))
        plt.plot(df_live['timestamp'], df_live['running_clients'], label='# of clients')
        plt.plot(df_live['timestamp'], df_live['running_servers'], label='# of Triton servers')
        plt.xlabel('Time')
        plt.ylabel('Count')
        plt.ylim(bottom=0)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.legend()
        plt.gca().set_aspect('auto', adjustable='box')
        plt.tight_layout()
        plt.savefig(os.path.join(run_dir, f'clients_servers_vs_time_{key}.png'))
        plt.close()
        # Plot latency/gpu vs. time
        df_live['total_latency_ms'] = pd.to_numeric(df_live['total_latency'], errors='coerce')
        df_live['gpu_util_percent'] = pd.to_numeric(df_live['gpu_util'], errors='coerce') * 100
        fig, ax1 = plt.subplots(figsize=(8, 8))
        color1 = 'tab:blue'
        color2 = 'tab:orange'
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Total Latency (ms)', color=color1)
        ax1.plot(df_live['timestamp'], df_live['total_latency_ms'], color=color1, label='Total Latency (ms)')
        ax1.tick_params(axis='y', labelcolor=color1)
        ax1.set_ylim(bottom=0)
        ax2 = ax1.twinx()
        ax2.set_ylabel('GPU Utilization (%)', color=color2)
        ax2.plot(df_live['timestamp'], df_live['gpu_util_percent'], color=color2, label='GPU Utilization (%)')
        ax2.tick_params(axis='y', labelcolor=color2)
        ax2.set_ylim(0, 100)
        fig.tight_layout()
        fig.axes[0].set_aspect('auto', adjustable='box')
        plt.savefig(os.path.join(run_dir, f'latency_gpu_vs_time_{key}.png'))
        plt.close()

    # 2. Scatter plot: one point per sequence, aggregating all data from that sequence
    agg_rows = []
    for key in keys:
        results_csv = os.path.join(run_dir, f'sonic_benchmark_results_{key}.csv')
        live_metrics_csv = os.path.join(run_dir, f'sonic_benchmark_live_metrics_{key}.csv')
        if not os.path.exists(results_csv) or not os.path.exists(live_metrics_csv):
            continue
        df_results = pd.read_csv(results_csv)
        if df_results.empty:
            continue
        # For GPU util, skip first minute of live metrics
        df_live = pd.read_csv(live_metrics_csv)
        df_live['timestamp'] = pd.to_datetime(df_live['timestamp'])
        if not df_live.empty:
            t0 = df_live['timestamp'].min()
            df_live_skip = df_live[df_live['timestamp'] >= t0 + pd.Timedelta(seconds=60)]
            gpu_util_avg_mean = pd.to_numeric(df_live_skip['gpu_util'], errors='coerce').mean()
            gpu_util_avg_std = pd.to_numeric(df_live_skip['gpu_util'], errors='coerce').std()
        else:
            gpu_util_avg_mean = float('nan')
            gpu_util_avg_std = float('nan')
        # Aggregate all data from the sequence for latency
        avg_latency_us_mean = df_results['avg_latency_us'].mean()
        avg_latency_us_std = df_results['avg_latency_us'].std()
        agg_rows.append({
            'key': key,
            'label': SEQUENCE_LABELS.get(key, key),
            'avg_latency_ms': avg_latency_us_mean / 1000.0,
            'avg_latency_ms_std': avg_latency_us_std / 1000.0,
            'gpu_util_percent': gpu_util_avg_mean * 100 if pd.notnull(gpu_util_avg_mean) else float('nan'),
            'gpu_util_percent_std': gpu_util_avg_std * 100 if pd.notnull(gpu_util_avg_std) else float('nan'),
        })
    if agg_rows:
        agg_df = pd.DataFrame(agg_rows)
        plt.figure(figsize=(8, 8))
        # Connect the non-SuperSONIC dots in the order of keys
        normal_ordered = pd.DataFrame([row for row in agg_rows if row['label'] != 'SuperSONIC'])
        if not normal_ordered.empty:
            # Use the order of keys for connection
            normal_ordered['key'] = pd.Categorical(normal_ordered['key'], categories=keys, ordered=True)
            normal_ordered = normal_ordered.sort_values('key')
            plt.scatter(
                normal_ordered['avg_latency_ms'], normal_ordered['gpu_util_percent'],
                color='tab:blue', label=None
            )
            plt.plot(
                normal_ordered['avg_latency_ms'], normal_ordered['gpu_util_percent'],
                color='tab:blue', linestyle='-', linewidth=2, alpha=0.7, zorder=2
            )
        # Plot SuperSONIC in red if present
        super_sonic = agg_df[agg_df['label'] == 'SuperSONIC']
        if not super_sonic.empty:
            plt.scatter(
                super_sonic['avg_latency_ms'], super_sonic['gpu_util_percent'],
                color='tab:red', label='SuperSONIC', zorder=3
            )
        axis_labelsize = plt.gca().yaxis.label.get_size()
        for _, row in agg_df.iterrows():
            if row['label'] == 'SuperSONIC':
                color = 'tab:red'
                plt.annotate(row['label'], (row['avg_latency_ms'], row['gpu_util_percent']),
                             textcoords="offset points", xytext=(-5, 2), ha='right', va='bottom', fontsize=axis_labelsize * 0.6, color=color)
            else:
                color = 'tab:blue'
                plt.annotate(row['label'], (row['avg_latency_ms'], row['gpu_util_percent']),
                             textcoords="offset points", xytext=(6, -4), ha='left', va='top', fontsize=axis_labelsize * 0.6, color=color)
        plt.xlabel('Average Latency (ms)')
        plt.ylabel('Average GPU Utilization (%)')
        plt.xlim(left=0, right=agg_df['avg_latency_ms'].max() * 1.2 if not agg_df['avg_latency_ms'].empty else None)
        plt.ylim(0, 100)
        plt.tight_layout()
        plt.savefig(os.path.join(run_dir, 'latency_vs_gpu_scatter.png'))
        plt.close() 