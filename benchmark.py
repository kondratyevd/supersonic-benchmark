# Main experiment loop for the benchmark
import time
import pandas as pd
import csv
from config import COLUMNS, OUTPUT_CSV, LIVE_METRICS_CSV
from kube_utils import set_service_mode, scale_deployment
from client_job import run_client_job

def run_experiment_sequence(experiment_sequence):
    pd.DataFrame(columns=COLUMNS).to_csv(OUTPUT_CSV, index=False)
    with open(LIVE_METRICS_CSV, "w", newline="") as live_metrics_file:
        live_metrics_writer = csv.DictWriter(live_metrics_file, fieldnames=[
            "timestamp", "running_clients", "running_servers", "envoy_overhead", "gpu_util"
        ])
        live_metrics_writer.writeheader()

        for exp in experiment_sequence:
            mode = exp["mode"]
            n_clients = exp["n_clients"]
            n_servers = exp["n_servers"]
            restart_servers = exp.get("restart_servers", True)

            set_service_mode(mode)
            scale_deployment("sonic-server-triton", "cms", n_servers, reset=restart_servers)

            df_clients = run_client_job(n_clients, mode, n_servers, live_metrics_writer=live_metrics_writer)
            df_clients["mode"] = mode
            df_clients["n_servers"] = n_servers
            df_clients = df_clients[COLUMNS]
            df_clients.to_csv(OUTPUT_CSV, mode="a", index=False, header=False)

            print(f"[Mode={mode}] Recorded n_servers={n_servers}, n_clients={n_clients}")

    print("Data collection complete. Results saved to sonic_benchmark_results.csv and sonic_benchmark_live_metrics.csv")

if __name__ == "__main__":
    EXPERIMENT_SEQUENCE = [
        {"mode": "supersonic", "n_clients": 20, "n_servers": 1, "restart_servers": True},
        {"mode": "bare_triton", "n_clients": 20, "n_servers": 2, "restart_servers": False},
        # {"mode": "supersonic", "n_clients": 30, "n_servers": 1, "restart_servers": False},
    ]
    run_experiment_sequence(EXPERIMENT_SEQUENCE) 