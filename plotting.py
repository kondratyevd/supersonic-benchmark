import os
import pandas as pd
import matplotlib.pyplot as plt
import mplhep
import re
import matplotlib.dates as mdates
import seaborn as sns
from glob import glob
from datetime import datetime
import sys
import warnings

# Add logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def safe_read_csv(file_path):
    """
    Safely read a CSV file, handling empty files and other errors.
    Returns None if the file is empty or cannot be read.
    """
    try:
        if not os.path.exists(file_path):
            return None
        df = pd.read_csv(file_path)
        if df.empty:
            return None
        return df
    except pd.errors.EmptyDataError:
        return None
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None

def plot_results(results_dir, keys):
    """
    Plot results from the benchmark runs.
    results_dir: directory containing the results
    keys: list of sequence keys to plot
    """
    logger.info(f"Starting to plot results from {results_dir}")
    logger.info(f"Looking for sequences: {keys}")
    
    if not os.path.exists(results_dir):
        logger.error(f"Results directory does not exist: {results_dir}")
        sys.exit(1)
    
    # Create plots directory
    plots_dir = os.path.join(results_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    logger.info(f"Created plots directory at {plots_dir}")
    
    all_data = []
    for key in keys:
        seq_dir = os.path.join(results_dir, key)
        if not os.path.exists(seq_dir):
            continue
        # No rep_* subdirs, just files
        rep_results = sorted(glob(os.path.join(seq_dir, 'results_rep*.csv')))
        rep_live = sorted(glob(os.path.join(seq_dir, 'live_metrics_rep*.csv')))
        rep_averages = []
        for results_csv, live_metrics_csv in zip(rep_results, rep_live):
            df = safe_read_csv(results_csv)
            df_live = safe_read_csv(live_metrics_csv)
            if df is not None and not df.empty and df_live is not None and not df_live.empty:
                rep_avg = {
                    'sequence': key,
                    'avg_latency_ms': df['avg_latency_us'].mean() / 1000.0,
                    'gpu_util_percent': df_live['gpu_util'].mean() * 100
                }
                rep_averages.append(rep_avg)
        if rep_averages:
            gpu_utils = [r['gpu_util_percent'] for r in rep_averages]
            print(f"Scatter plot GPU util values for {key}: {gpu_utils}")
            rep_df = pd.DataFrame(rep_averages)
            agg_data = {
                'sequence': key,
                'avg_latency_ms_mean': rep_df['avg_latency_ms'].mean(),
                'avg_latency_ms_std': rep_df['avg_latency_ms'].std(),
                'gpu_util_percent_mean': rep_df['gpu_util_percent'].mean(),
                'gpu_util_percent_std': rep_df['gpu_util_percent'].std()
            }
            all_data.append(agg_data)
        # For time series, use the new file structure
        rep_results = sorted(glob(os.path.join(seq_dir, 'results_rep*.csv')))
        rep_live = sorted(glob(os.path.join(seq_dir, 'live_metrics_rep*.csv')))
        if not rep_results or not rep_live:
            continue
        all_timestamps = []
        fig, axes = plt.subplots(4, 1, figsize=(14, 9), sharex=True, gridspec_kw={'hspace': 0.25})
        colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:purple']
        panel_labels = [
            'Perf. Analyzer Clients',
            'Triton Servers',
            'Total Latency, ms',
            'Avg. GPU util, %'
        ]
        # Store all y data for headroom calculation
        y_data = [[], [], [], []]
        for live_metrics_csv in rep_live:
            df = safe_read_csv(live_metrics_csv)
            if df is not None:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                all_timestamps.append(df['timestamp'].min())
                y_data[0].extend(df['running_clients'])
                y_data[1].extend(df['running_servers'])
                y_data[2].extend(df['total_latency'])
                y_data[3].extend(df['gpu_util'] * 100)
                axes[0].plot(df['timestamp'], df['running_clients'], color=colors[0], linewidth=4)
                axes[1].plot(df['timestamp'], df['running_servers'], color=colors[1], linewidth=4)
                axes[2].plot(df['timestamp'], df['total_latency'], color=colors[2], linewidth=4)
                axes[3].plot(df['timestamp'], df['gpu_util'] * 100, color=colors[3], linewidth=4)
        for ax in axes:
            ax.set_ylabel("")
        for i, ax in enumerate(axes):
            ax.legend([panel_labels[i]], loc='upper left', frameon=False)
        # Set y-axis ranges with 20% headroom except for GPU util
        for i, ax in enumerate(axes):
            if i < 3 and y_data[i]:
                ymax = max(y_data[i])
                ax.set_ylim(0, ymax * 1.2 if ymax > 0 else 1)
            elif i == 3:
                ax.set_ylim(0, 100)
        axes[3].set_xlabel('Time')
        axes[3].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        if all_timestamps:
            min_time = min(all_timestamps)
            max_time = max(all_timestamps)
            total_range = max_time - min_time
            pad_left = min_time - total_range * 0.75
            axes[3].set_xlim(left=pad_left)
        for ax in axes[:-1]:
            ax.label_outer()
        for ax in axes:
            ax.grid(True, alpha=0.5)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            plt.tight_layout()
        plot_path = os.path.join(plots_dir, f'clients_servers_latency_gpu_vs_time_{key}.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved time series plot to {plot_path}")
        plt.close()

    if all_data:
        logger.info("Creating scatter plots")
        agg_df = pd.DataFrame(all_data)
        # --- GPU vs Latency ---
        plt.figure(figsize=(10, 10))
        triton_color = 'tab:blue'
        supersonic_color = 'tab:red'
        triton_points = []
        for idx, row in agg_df.iterrows():
            if row['sequence'].startswith('triton_'):
                # Extract number of servers from key, e.g., 'triton_1server' -> 1
                match = re.search(r'triton_(\d+)', row['sequence'])
                n_servers = int(match.group(1)) if match else 0
                color = triton_color
                triton_points.append((n_servers, row['avg_latency_ms_mean'], row['gpu_util_percent_mean']))
            elif row['sequence'] == 'supersonic':
                color = supersonic_color
            else:
                color = 'gray'
            plt.errorbar(
                row['avg_latency_ms_mean'],
                row['gpu_util_percent_mean'],
                xerr=row['avg_latency_ms_std'],
                yerr=row['gpu_util_percent_std'],
                fmt='o',
                color=color,
                capsize=5,
                markersize=8,
                linewidth=2
            )
            tick_fontsize = plt.gca().xaxis.get_ticklabels()[0].get_fontsize() if plt.gca().xaxis.get_ticklabels() else 12
            label_text = SEQUENCE_LABELS.get(row['sequence'], row['sequence'])
            plt.annotate(
                label_text,
                (row['avg_latency_ms_mean'], row['gpu_util_percent_mean']),
                textcoords="offset points", xytext=(8,-24), ha='left', fontsize=tick_fontsize,
                color=color
            )
        if triton_points:
            # Sort by number of servers (first element)
            triton_points = sorted(triton_points, key=lambda x: x[0])
            plt.plot(
                [p[1] for p in triton_points],  # avg_latency_ms_mean
                [p[2] for p in triton_points],  # gpu_util_percent_mean
                color=triton_color,
                linewidth=2,
                zorder=1
            )
        plt.xlabel('Average Latency (ms)')
        plt.ylabel('Average GPU Utilization (%)')
        plt.ylim(0, 100)
        if not agg_df['avg_latency_ms_mean'].empty:
            xmax = agg_df['avg_latency_ms_mean'].max() * 1.2
            plt.xlim(left=0, right=xmax)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plot_path = os.path.join(plots_dir, 'gpu_vs_latency_scatter.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved GPU util vs latency scatter plot to {plot_path}")
        plt.close()
    else:
        logger.warning("No data found for scatter plots")

if __name__ == "__main__":
    # Get the most recent results directory
    results_dirs = sorted(glob("results/multiseq_*"))
    if not results_dirs:
        logger.error("No results directories found")
        sys.exit(1)
    
    latest_results = results_dirs[-1]
    logger.info(f"Using latest results directory: {latest_results}")
    
    # Define the sequences to plot
    keys = [
        'triton_1server', 'triton_2servers', 'triton_3servers', 'triton_4servers',
        'triton_5servers', 'triton_6servers', 'triton_7servers', 'triton_8servers',
        'triton_9servers', 'triton_10servers', 'supersonic'
    ]
    
    plot_results(latest_results, keys) 