# Metrics and Prometheus querying functions for the benchmark
import requests
import numpy as np
from config import PROMETHEUS_URL, DEPLOYMENT_NAME

def query_envoy_overhead() -> float or None:
    query = (
        (
            'sum by (pod)('
            'increase(envoy_http_downstream_rq_time_sum{release="' + str(DEPLOYMENT_NAME) + '",envoy_http_conn_manager_prefix="ingress_grpc"}[30s])'
            ' / '
            'increase(envoy_http_downstream_rq_time_count{release="' + str(DEPLOYMENT_NAME) + '",envoy_http_conn_manager_prefix="ingress_grpc"}[30s])'
            ')'
            ' - '
            'sum by (pod)('
            'increase(envoy_cluster_upstream_rq_time_sum{release="' + str(DEPLOYMENT_NAME) + '"}[30s])'
            ' / '
            'increase(envoy_cluster_upstream_rq_time_count{release="' + str(DEPLOYMENT_NAME) + '"}[30s])'
            ')'
        )
    )
    response = requests.get(PROMETHEUS_URL, params={"query": query}, verify=True)
    response.raise_for_status()
    data = response.json().get("data", {}).get("result", [])
    values = [
        float(item["value"][1])
        for item in data
        if item.get("value") and item["value"][1] not in ("NaN", "0")
    ]
    if not values:
        return None
    total = sum(values)
    print(f"Prometheus envoy_overhead sample: {total}")
    return total

def query_gpu_utilization() -> float or None:
    query = 'avg by(gpu)(avg_over_time(nv_gpu_utilization[30s]))'
    response = requests.get(PROMETHEUS_URL, params={"query": query}, verify=True)
    response.raise_for_status()
    data = response.json().get("data", {}).get("result", [])
    values = [
        float(item["value"][1])
        for item in data
        if item.get("value") and item["value"][1] not in ("NaN", "0")
    ]
    if not values:
        return None
    avg_util = float(np.mean(values))
    print(f"Prometheus gpu_utilization sample: {avg_util}")
    return avg_util

def query_total_latency() -> float or None:
    query = (
        (
            'sum by (pod)('
            'increase(envoy_http_downstream_rq_time_sum{release="' + str(DEPLOYMENT_NAME) + '",envoy_http_conn_manager_prefix="ingress_grpc"}[30s])'
            ' / '
            'increase(envoy_http_downstream_rq_time_count{release="' + str(DEPLOYMENT_NAME) + '",envoy_http_conn_manager_prefix="ingress_grpc"}[30s])'
            ')'
        )
    )
    response = requests.get(PROMETHEUS_URL, params={"query": query}, verify=True)
    response.raise_for_status()
    data = response.json().get("data", {}).get("result", [])
    values = [
        float(item["value"][1])
        for item in data
        if item.get("value") and item["value"][1] not in ("NaN", "0")
    ]
    if not values:
        return None
    total = sum(values)
    print(f"Prometheus total_latency sample: {total}")
    return total 