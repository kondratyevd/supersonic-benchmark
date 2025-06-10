# Main experiment loop for the benchmark
import time
import pandas as pd
import csv
import os
from config import COLUMNS, OUTPUT_CSV, LIVE_METRICS_CSV
from kube_utils import set_service_mode, scale_deployment
from client_job import run_client_job
from datetime import datetime
from plotting import plot_results

def run_experiment_sequences(sequences_dict):
    """
    sequences_dict: dict of {key: sequence_list}
    Returns: (run_dir, list of keys)
    """
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    run_dir = os.path.join('results', f'multiseq_{timestamp}')
    os.makedirs(run_dir, exist_ok=True)
    keys = list(sequences_dict.keys())
    for key, experiment_sequence in sequences_dict.items():
        output_csv = os.path.join(run_dir, f'sonic_benchmark_results_{key}.csv')
        live_metrics_csv = os.path.join(run_dir, f'sonic_benchmark_live_metrics_{key}.csv')
        pd.DataFrame(columns=COLUMNS).to_csv(output_csv, index=False)
        with open(live_metrics_csv, "w", newline="") as live_metrics_file:
            live_metrics_writer = csv.DictWriter(live_metrics_file, fieldnames=[
                "timestamp", "running_clients", "running_servers", "envoy_overhead", "gpu_util", "total_latency"
            ])
            live_metrics_writer.writeheader()
            for exp in experiment_sequence:
                mode = exp["mode"]
                n_clients = exp["n_clients"]
                n_servers = exp["n_servers"]
                restart_servers = exp.get("restart_servers", True)
                print(f"[{key}] [Mode={mode}] Running n_servers={n_servers}, n_clients={n_clients}")
                set_service_mode(mode)
                scale_deployment("sonic-server-triton", "cms", n_servers, mode, reset=restart_servers)
                if restart_servers:
                    print("Sleeping for 30s after server restart...")
                    time.sleep(30)
                request_count = exp.get("request_count", 5000)
                df_clients = run_client_job(n_clients, mode, n_servers, live_metrics_writer=live_metrics_writer, request_count=request_count)
                df_clients["mode"] = mode
                df_clients["n_servers"] = n_servers
                df_clients = df_clients[COLUMNS]
                df_clients.to_csv(output_csv, mode="a", index=False, header=False)
                # print(f"[{key}] [Mode={mode}] Recorded n_servers={n_servers}, n_clients={n_clients}")
    print(f"Data collection complete. Results saved in {run_dir}")
    return run_dir, keys

if __name__ == "__main__":
    SEQUENCES = {
        "triton_1server": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 1, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 1, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 1, "request_count": 20000, "restart_servers": False},
        ],
        "triton_2servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 2, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 2, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 2, "request_count": 20000, "restart_servers": False},
        ],
        "triton_3servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 3, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 3, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 3, "request_count": 20000, "restart_servers": False},
        ],
        "triton_4servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 4, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 4, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 4, "request_count": 20000, "restart_servers": False},
        ],
        "triton_5servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 5, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 5, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 5, "request_count": 20000, "restart_servers": False},
        ],
        "triton_6servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 6, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 6, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 6, "request_count": 20000, "restart_servers": False},
        ],
        "triton_7servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 7, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 7, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 7, "request_count": 20000, "restart_servers": False},
        ],
        "triton_8servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 8, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 8, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 8, "request_count": 20000, "restart_servers": False},
        ],
        "triton_9servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 9, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 9, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 9, "request_count": 20000, "restart_servers": False},
        ],
        "triton_10servers": [
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 10, "request_count": 20000, "restart_servers": True},
            {"mode": "bare_triton", "n_clients": 10, "n_servers": 10, "request_count": 10000, "restart_servers": False},
            {"mode": "bare_triton", "n_clients": 1, "n_servers": 10, "request_count": 20000, "restart_servers": False},
        ],
        "supersonic": [
            {"mode": "supersonic", "n_clients": 1, "n_servers": 1, "request_count": 20000, "restart_servers": True},
            {"mode": "supersonic", "n_clients": 10, "n_servers": 1, "request_count": 10000, "restart_servers": False},
            {"mode": "supersonic", "n_clients": 1, "n_servers": 1, "request_count": 20000, "restart_servers": False},
        ],
    }
    results_dir, keys = run_experiment_sequences(SEQUENCES)
    plot_results(results_dir, keys)
 
    # results_dir = "results/multiseq_20250609_213819"
    # keys = ["triton_1server", "triton_2servers", "triton_3servers", "triton_4servers", "triton_5servers", "triton_6servers", "triton_7servers", "triton_8servers", "triton_9servers", "triton_10servers", "supersonic"]
    # plot_results(results_dir, keys) 