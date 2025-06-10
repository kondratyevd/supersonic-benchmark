# Client job execution and log parsing for the benchmark
import time
import uuid
import re
import pandas as pd
import numpy as np
from kubernetes import client
from datetime import datetime
from config import (NAMESPACE, SUPRASONIC_SERVICE, BARE_TRITON_SERVICE, JOB_BASE_NAME, CONTAINER_IMAGE, CONTAINER_NAME, REQUEST_COUNT, SERVICE_ACCOUNT_NAME, RESOURCES, METRIC_PATTERNS, COLUMNS)
from kube_utils import count_running_pods, count_running_servers
from metrics import query_envoy_overhead, query_gpu_utilization, query_total_latency

def log_live_metrics(live_metrics_writer, mode, n_clients, n_servers, running_clients, running_servers, envoy_overhead, gpu_util, total_latency):
    timestamp = datetime.utcnow().isoformat()
    row = {
        "timestamp": timestamp,
        "running_clients": running_clients,
        "running_servers": running_servers,
        "envoy_overhead": envoy_overhead,
        "gpu_util": gpu_util,
        "total_latency": total_latency,
    }
    live_metrics_writer.writerow(row)

def run_client_job(n_clients: int, mode: str, n_servers: int, live_metrics_writer=None, request_count: int = 5000):
    if mode == "supersonic":
        endpoint_url = f"{SUPRASONIC_SERVICE}.{NAMESPACE}.svc.cluster.local:8001"
    else:
        endpoint_url = f"{BARE_TRITON_SERVICE}.{NAMESPACE}.geddes.rcac.purdue.edu:8001"

    job_name = f"{JOB_BASE_NAME}-{str(uuid.uuid4())[:8]}"

    barrier_script = f'''
echo "Waiting for {n_clients} pods to reach Running..."
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
while true; do
  RESPONSE=$(curl -sSk \
    -H "Authorization: Bearer $TOKEN" \
    https://kubernetes.default.svc/api/v1/namespaces/{NAMESPACE}/pods?labelSelector=job-name={job_name} \
    || echo '{{"failure":true}}')
  RUNNING_COUNT=$(echo "$RESPONSE" | grep -oE '"phase"\\s*:\\s*"Running"' | wc -l || echo 0)
  if [ "$RUNNING_COUNT" -ge "{n_clients}" ]; then
    break
  fi
  sleep 2
done

# perf_analyzer -i grpc \
#   -m deepmet -x 1 \
#   -u {endpoint_url} \
#   --async -p 1 \
#   -b 20 \
#   --request-count={request_count} \
#   --concurrency-range=1 --input-data "random"

perf_analyzer -m particlenet_AK4_PT -i grpc -u {endpoint_url} \
    --async -p 1 -b 100 --concurrency-range 1 \
    --shape pf_points__0:2,100 --shape pf_features__1:20,100 --shape pf_mask__2:1,100 --shape sv_points__3:2,10 --shape sv_features__4:11,10 --shape sv_mask__5:1,10 \
    --request-count={request_count}
'''
    container_args = ["-c", barrier_script]

    pod_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"job-name": job_name}),
        spec=client.V1PodSpec(
            restart_policy="OnFailure",
            service_account_name=SERVICE_ACCOUNT_NAME,
            containers=[
                client.V1Container(
                    name=CONTAINER_NAME,
                    image=CONTAINER_IMAGE,
                    command=["/bin/bash"],
                    args=container_args,
                    resources=RESOURCES,
                )
            ],
        ),
    )

    job_spec = client.V1JobSpec(
        parallelism=n_clients,
        completions=n_clients,
        backoff_limit=1000,
        template=pod_template,
    )

    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name, namespace=NAMESPACE),
        spec=job_spec,
    )

    batch_v1 = client.BatchV1Api()
    core_v1 = client.CoreV1Api()
    batch_v1.create_namespaced_job(namespace=NAMESPACE, body=job)

    envoy_samples = []
    gpu_samples   = []
    while True:
        status = batch_v1.read_namespaced_job(name=job_name, namespace=NAMESPACE).status
        succeeded = status.succeeded or 0
        failed    = status.failed    or 0
        if succeeded == n_clients or failed >= n_clients:
            break

        e_sample = query_envoy_overhead()
        if e_sample is not None and e_sample != 0:
            envoy_samples.append(e_sample)
        g_sample = query_gpu_utilization()
        if g_sample is not None and g_sample != 0:
            gpu_samples.append(g_sample)
        t_sample = query_total_latency()

        if live_metrics_writer:
            running_clients = count_running_pods(f"job-name={job_name}", NAMESPACE)
            running_servers = count_running_servers(NAMESPACE)
            if mode == "supersonic":
                if (e_sample is not None and g_sample is not None and t_sample is not None 
                    and running_clients is not None and running_servers is not None):
                    log_live_metrics(
                        live_metrics_writer, mode, n_clients, n_servers,
                        running_clients, running_servers, e_sample, g_sample, t_sample
                    )
            else:
                log_live_metrics(
                    live_metrics_writer, mode, n_clients, n_servers,
                    running_clients, running_servers, e_sample, g_sample, t_sample
                )

        time.sleep(5)

    if envoy_samples:
        envoy_overhead_avg = float(np.mean(envoy_samples))
        envoy_overhead_std = float(np.std(envoy_samples))
    else:
        envoy_overhead_avg = None
        envoy_overhead_std = None

    if gpu_samples:
        gpu_util_avg = float(np.mean(gpu_samples))
        gpu_util_std = float(np.std(gpu_samples))
    else:
        gpu_util_avg = None
        gpu_util_std = None

    print(f"[Mode={mode}, n_clients={n_clients}] envoy: avg={envoy_overhead_avg}, std={envoy_overhead_std}")
    print(f"[Mode={mode}, n_clients={n_clients}] gpu_util: avg={gpu_util_avg}, std={gpu_util_std}")

    pods = core_v1.list_namespaced_pod(namespace=NAMESPACE, label_selector=f"job-name={job_name}").items
    records = []
    for pod in pods:
        pod_name = pod.metadata.name
        log_text = core_v1.read_namespaced_pod_log(name=pod_name, namespace=NAMESPACE)

        rec = {"n_clients": n_clients, "pod_name": pod_name}
        for key, pattern in METRIC_PATTERNS.items():
            m = re.search(pattern, log_text)
            if m:
                val_str = m.group(1)
                rec[key] = float(val_str) if "." in val_str else int(val_str)
            else:
                rec[key] = None
        rec["envoy_overhead_avg"] = envoy_overhead_avg
        rec["envoy_overhead_std"] = envoy_overhead_std
        rec["gpu_util_avg"] = gpu_util_avg
        rec["gpu_util_std"] = gpu_util_std
        records.append(rec)

    batch_v1.delete_namespaced_job(
        name=job_name,
        namespace=NAMESPACE,
        body=client.V1DeleteOptions(propagation_policy="Background"),
    )

    df = pd.DataFrame(records)
    return df[[col for col in COLUMNS if col not in ['mode', 'n_servers']]] 