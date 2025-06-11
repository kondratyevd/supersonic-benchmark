#!/usr/bin/env python3

import os
import sys
import subprocess
from datetime import datetime

# Constants
POD_NAME = "sonic-benchmark-hztkr"  # Replace with your pod name
NAMESPACE = "cms"
RESULTS_BASE = "/work/users/dkondra/sonic-benchmark/results"
SPECIFIC_RESULTS_DIR = "/work/users/dkondra/sonic-benchmark/results/multiseq_20250611_141604"  # Set to a specific directory path if needed

def download_results():
    """
    Download results from a running benchmark pod.
    Uses constants defined at the top of the file for configuration.
    """
    # First, check if the pod exists
    try:
        subprocess.run(
            ["kubectl", "get", "pod", POD_NAME, "-n", NAMESPACE],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        print(f"Error: Pod {POD_NAME} not found in namespace {NAMESPACE}")
        sys.exit(1)
    
    # Create local results directory if it doesn't exist
    local_results_dir = "results"
    os.makedirs(local_results_dir, exist_ok=True)
    
    # Get the timestamp from the results directory
    results_dir = SPECIFIC_RESULTS_DIR
    timestamp = os.path.basename(results_dir)
    local_dir = os.path.join(local_results_dir, timestamp)
    
    print(f"Downloading results from {results_dir} to {local_dir}")
    
    # Create a tar archive of the results directory in the pod
    try:
        subprocess.run(
            ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--", "tar", "czf", "-", "-C", os.path.dirname(results_dir), os.path.basename(results_dir)],
            stdout=open(os.path.join(local_dir + ".tar.gz"), "wb"),
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error creating tar archive: {e}")
        sys.exit(1)
    
    # Extract the archive locally
    try:
        subprocess.run(
            ["tar", "xzf", os.path.join(local_dir + ".tar.gz"), "-C", local_results_dir],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error extracting archive: {e}")
        sys.exit(1)
    
    # Clean up the tar file
    os.remove(os.path.join(local_dir + ".tar.gz"))
    
    print(f"Results downloaded to {local_dir}")
    print(f"Contents:")
    subprocess.run(["ls", "-R", local_dir])

if __name__ == "__main__":
    download_results() 