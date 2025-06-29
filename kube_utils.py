# Kubernetes utility functions for the benchmark
import time
from kubernetes import client
from config import NAMESPACE, BARE_TRITON_SERVICE, DEPLOYMENT_NAME, POLL_INTERVAL_SECONDS

core_api = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
custom_api = client.CustomObjectsApi()


def delete_service(name: str, namespace: str):
    try:
        core_api.delete_namespaced_service(name=name, namespace=namespace)
        time.sleep(3)
    except client.exceptions.ApiException as e:
        if e.status != 404:
            raise

def create_headless_service():
    svc_metadata = client.V1ObjectMeta(
        name=BARE_TRITON_SERVICE,
        namespace=NAMESPACE,
        labels={
            "app.kubernetes.io/component": "triton",
            "app.kubernetes.io/instance": "sonic-server",
            "app.kubernetes.io/name": "supersonic",
            "scrape_metrics": "true"
        },
    )
    svc_spec = client.V1ServiceSpec(
        cluster_ip="None",
        type="ClusterIP",
        selector={
            "app.kubernetes.io/component": "triton",
            "app.kubernetes.io/instance": "sonic-server",
            "app.kubernetes.io/name": "supersonic",
        },
        ports=[
            client.V1ServicePort(name="http", port=8000, target_port=8000),
            client.V1ServicePort(name="grpc", port=8001, target_port=8001),
            client.V1ServicePort(name="metrics", port=8002, target_port=8002),
        ],
    )
    svc = client.V1Service(api_version="v1", kind="Service", metadata=svc_metadata, spec=svc_spec)
    core_api.create_namespaced_service(namespace=NAMESPACE, body=svc)
    time.sleep(5)

def create_loadbalancer_service():
    svc_metadata = client.V1ObjectMeta(
        name=BARE_TRITON_SERVICE,
        namespace=NAMESPACE,
        labels={
            "app.kubernetes.io/component": "triton",
            "app.kubernetes.io/instance": "sonic-server",
            "app.kubernetes.io/name": "supersonic",
            "scrape_metrics": "true"
        },
    )
    svc_spec = client.V1ServiceSpec(
        type="LoadBalancer",
        selector={
            "app.kubernetes.io/component": "triton",
            "app.kubernetes.io/instance": "sonic-server",
            "app.kubernetes.io/name": "supersonic",
        },
        ports=[
            client.V1ServicePort(name="http", port=8000, target_port=8000),
            client.V1ServicePort(name="grpc", port=8001, target_port=8001),
            client.V1ServicePort(name="metrics", port=8002, target_port=8002),
        ],
    )
    svc = client.V1Service(api_version="v1", kind="Service", metadata=svc_metadata, spec=svc_spec)
    core_api.create_namespaced_service(namespace=NAMESPACE, body=svc)
    time.sleep(5)

def set_service_mode(mode: str):
    delete_service(BARE_TRITON_SERVICE, NAMESPACE)
    if mode == "supersonic":
        create_headless_service()
    elif mode == "bare_triton":
        create_loadbalancer_service()
    else:
        raise ValueError("Mode must be 'supersonic' or 'bare_triton'")

def scale_deployment(name: str, namespace: str, replicas: int, mode: str, reset: bool = False):
    """
    Patch the KEDA ScaledObject:
    - If mode is 'supersonic', set minReplicaCount=1 and maxReplicaCount=10 (autoscale allowed).
    - If mode is 'bare_triton', set minReplicaCount=maxReplicaCount=replicas (disable autoscale).
    Then scale the deployment.
    """
    scaledobject_name = "sonic-server-keda-so"
    group = "keda.sh"
    version = "v1alpha1"
    plural = "scaledobjects"
    try:
        if mode == "supersonic":
            patch = {"spec": {"minReplicaCount": 1, "maxReplicaCount": 10}}
            print(f"Patched KEDA ScaledObject {scaledobject_name} min/max replicas to 1/10 (supersonic mode)")
        else:
            patch = {"spec": {"minReplicaCount": replicas, "maxReplicaCount": replicas}}
            print(f"Patched KEDA ScaledObject {scaledobject_name} min/max replicas to {replicas} (bare_triton mode)")
        custom_api.patch_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=plural,
            name=scaledobject_name,
            body=patch
        )
    except Exception as e:
        import traceback
        print(f"Failed to patch KEDA ScaledObject: {e}")
        traceback.print_exc()

    if reset:
        patch_zero = {"spec": {"replicas": 0}}
        apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=patch_zero)
        while True:
            dep = apps_v1.read_namespaced_deployment(name=name, namespace=namespace).status
            available = dep.available_replicas or 0
            if available == 0:
                break
            time.sleep(POLL_INTERVAL_SECONDS)

    patch_body = {"spec": {"replicas": replicas}}
    apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=patch_body)
    while True:
        dep = apps_v1.read_namespaced_deployment(name=name, namespace=namespace).status
        available = dep.available_replicas or 0
        if available >= replicas:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

def count_running_pods(label_selector: str, namespace: str) -> int:
    pods = core_api.list_namespaced_pod(namespace=namespace, label_selector=label_selector).items
    return sum(1 for pod in pods if pod.status.phase == "Running")

def count_running_servers(namespace: str) -> int:
    pods = core_api.list_namespaced_pod(namespace=namespace, label_selector="app.kubernetes.io/component=triton").items
    return sum(1 for pod in pods if pod.status.phase == "Running")

def cleanup_benchmark_jobs(namespace="cms"):
    """Delete all existing benchmark-related jobs and pods"""
    batch_v1 = client.BatchV1Api()
    v1 = client.CoreV1Api()
    
    # Delete jobs with our label
    try:
        jobs = batch_v1.list_namespaced_job(
            namespace=namespace,
            label_selector="app=sonic-benchmark"
        )
        for job in jobs.items:
            print(f"Deleting existing job: {job.metadata.name}")
            batch_v1.delete_namespaced_job(
                name=job.metadata.name,
                namespace=namespace,
                body=client.V1DeleteOptions(propagation_policy="Background")
            )
    except Exception as e:
        print(f"Error cleaning up jobs: {e}")
    
    # Delete pods that might be stuck
    try:
        pods = v1.list_namespaced_pod(
            namespace=namespace,
            label_selector="app=sonic-benchmark"
        )
        for pod in pods.items:
            print(f"Deleting existing pod: {pod.metadata.name}")
            v1.delete_namespaced_pod(
                name=pod.metadata.name,
                namespace=namespace,
                body=client.V1DeleteOptions(propagation_policy="Background")
            )
    except Exception as e:
        print(f"Error cleaning up pods: {e}") 