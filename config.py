from kubernetes import config as k8s_config
try:
    k8s_config.load_incluster_config()
except Exception:
    k8s_config.load_kube_config()

# Configuration constants and global variables for the benchmark
import numpy as np
from kubernetes import client

NAMESPACE             = "cms"
JOB_BASE_NAME         = "sonic-benchmark"
SUPRASONIC_SERVICE    = "sonic-server"
BARE_TRITON_SERVICE   = "sonic-server-triton"
DEPLOYMENT_NAME       = "sonic-server-triton"
CONTAINER_IMAGE       = "nvcr.io/nvidia/tritonserver:24.11-py3-sdk"
CONTAINER_NAME        = "perf-analyzer"
REQUEST_COUNT         = 5000
SERVICE_ACCOUNT_NAME  = "hub"   # must have 'list pods' permission

RESOURCES = client.V1ResourceRequirements(
    requests={"cpu": "1", "memory": "4G"},
    limits={"cpu": "1", "memory": "4G"},
)

POLL_INTERVAL_SECONDS = 5
PROMETHEUS_URL = "https://prometheus-af.geddes.rcac.purdue.edu/api/v1/query"

METRIC_PATTERNS = {
    "batch_size":             r"Batch size:\s+(\d+)",
    "throughput_ips":         r"Throughput:\s+([\d.]+)\s+infer/sec",
    "avg_latency_us":         r"Avg latency:\s+(\d+)\s+usec",
    "p50_latency_us":         r"p50 latency:\s+(\d+)\s+usec",
    "p90_latency_us":         r"p90 latency:\s+(\d+)\s+usec",
    "p95_latency_us":         r"p95 latency:\s+(\d+)\s+usec",
    "p99_latency_us":         r"p99 latency:\s+(\d+)\s+usec",
    "avg_request_latency_us": r"Avg request latency:\s+(\d+)\s+usec",
    "overhead_us":            r"overhead\s+(\d+)\s+usec",
    "queue_us":               r"queue\s+(\d+)\s+usec",
    "compute_input_us":       r"compute input\s+(\d+)\s+usec",
    "compute_infer_us":       r"compute infer\s+(\d+)\s+usec",
    "compute_output_us":      r"compute output\s+(\d+)\s+usec",
}

OUTPUT_CSV = "sonic_benchmark_results.csv"
LIVE_METRICS_CSV = "sonic_benchmark_live_metrics.csv"

COLUMNS = [
    'n_clients', 'pod_name', 'batch_size', 'throughput_ips', 'avg_latency_us', 'p50_latency_us', 'p90_latency_us',
    'p95_latency_us', 'p99_latency_us', 'avg_request_latency_us', 'overhead_us', 'queue_us', 'compute_input_us',
    'compute_infer_us', 'compute_output_us', 'envoy_overhead_avg', 'envoy_overhead_std', 'gpu_util_avg',
    'gpu_util_std', 'mode', 'n_servers'
]

LIVE_METRICS_COLUMNS = [
    "timestamp", "running_clients", "running_servers",
    "envoy_overhead", "gpu_util"
] 