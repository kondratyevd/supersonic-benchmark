import os
import yaml
from kubernetes import client, config
from kube_utils import cleanup_benchmark_jobs

# Try to load in-cluster config first, fall back to local kubeconfig
try:
    config.load_incluster_config()
    print("Using in-cluster configuration")
except config.ConfigException:
    try:
        config.load_kube_config()
        print("Using local kubeconfig")
    except config.ConfigException as e:
        print(f"Error loading kubeconfig: {e}")
        raise

def create_benchmark_job():
    batch_v1 = client.BatchV1Api()
    v1 = client.CoreV1Api()
    
    # Create ConfigMap with all necessary Python files
    files_to_include = [
        'benchmark.py',
        'client_job.py',
        'metrics.py',
        'plotting.py',
        'config.py',
        'kube_utils.py'
    ]
    
    data = {}
    for file in files_to_include:
        with open(file, 'r') as f:
            data[file] = f.read()
    
    configmap = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(
            name="benchmark-code",
            labels={"app": "sonic-benchmark"}
        ),
        data=data
    )
    
    try:
        v1.create_namespaced_config_map(namespace="cms", body=configmap)
    except client.exceptions.ApiException as e:
        if e.status == 409:  # Already exists
            v1.replace_namespaced_config_map(name="benchmark-code", namespace="cms", body=configmap)
        else:
            raise
    
    # Create a job that will run the benchmark
    job = client.V1Job(
        metadata=client.V1ObjectMeta(
            name="sonic-benchmark",
            labels={"app": "sonic-benchmark"}
        ),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": "sonic-benchmark"}
                ),
                spec=client.V1PodSpec(
                    service_account_name="benchmark-sa",  # Use the new service account
                    containers=[
                        client.V1Container(
                            name="benchmark",
                            image="python:3.9-slim",
                            command=["/bin/bash", "-c"],
                            args=["""
                                apt-get update && apt-get install -y git
                                mkdir -p /benchmark
                                cp /code/* /benchmark/
                                cd /benchmark
                                pip install kubernetes pandas numpy matplotlib seaborn mplhep
                                # Add the current directory to PYTHONPATH
                                export PYTHONPATH=/benchmark:$PYTHONPATH
                                python benchmark.py
                            """],
                            resources=client.V1ResourceRequirements(
                                requests={
                                    "memory": "2Gi",
                                    "cpu": "1"
                                },
                                limits={
                                    "memory": "4Gi",
                                    "cpu": "2"
                                }
                            ),
                            volume_mounts=[
                                client.V1VolumeMount(
                                    name="code",
                                    mount_path="/code"
                                ),
                                client.V1VolumeMount(
                                    name="af-shared-storage",
                                    mount_path="/work"
                                )
                            ]
                        )
                    ],
                    volumes=[
                        client.V1Volume(
                            name="code",
                            config_map=client.V1ConfigMapVolumeSource(
                                name="benchmark-code"
                            )
                        ),
                        client.V1Volume(
                            name="af-shared-storage",
                            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                claim_name="af-shared-storage"
                            )
                        )
                    ],
                    restart_policy="Never"
                )
            )
        )
    )
    
    try:
        batch_v1.create_namespaced_job(namespace="cms", body=job)
    except client.exceptions.ApiException as e:
        if e.status == 409:  # Already exists
            batch_v1.delete_namespaced_job(name="sonic-benchmark", namespace="cms")
            batch_v1.create_namespaced_job(namespace="cms", body=job)
        else:
            raise

def main():
    """Main function to run the benchmark on the cluster"""
    print("Cleaning up existing benchmark jobs...")
    cleanup_benchmark_jobs()
    
    print("Creating benchmark job...")
    create_benchmark_job()
    
    print("Benchmark job created! You can monitor the progress with:")
    print("kubectl get jobs -n cms -l app=sonic-benchmark")
    print("kubectl get pods -n cms -l app=sonic-benchmark")

if __name__ == "__main__":
    main() 