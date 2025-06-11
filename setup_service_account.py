import os
from kubernetes import client, config

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

def create_service_account():
    """Create a service account for the benchmark"""
    v1 = client.CoreV1Api()
    rbac_v1 = client.RbacAuthorizationV1Api()
    
    # Create ServiceAccount
    service_account = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name="benchmark-sa",
            namespace="cms"
        )
    )
    
    try:
        v1.create_namespaced_service_account(namespace="cms", body=service_account)
        print("Created ServiceAccount 'benchmark-sa'")
    except client.exceptions.ApiException as e:
        if e.status == 409:  # Already exists
            print("ServiceAccount 'benchmark-sa' already exists")
        else:
            raise
    
    # Create Role with necessary permissions
    role = client.V1Role(
        metadata=client.V1ObjectMeta(
            name="benchmark-role",
            namespace="cms"
        ),
        rules=[
            # Core API group permissions
            client.V1PolicyRule(
                api_groups=[""],
                resources=["pods", "pods/log", "configmaps", "services"],
                verbs=["get", "list", "watch", "create", "update", "patch", "delete"]
            ),
            # Batch API group permissions
            client.V1PolicyRule(
                api_groups=["batch"],
                resources=["jobs"],
                verbs=["get", "list", "watch", "create", "update", "patch", "delete"]
            ),
            # Apps API group permissions
            client.V1PolicyRule(
                api_groups=["apps"],
                resources=["deployments"],
                verbs=["get", "list", "watch", "create", "update", "patch", "delete"]
            ),
            # KEDA API group permissions
            client.V1PolicyRule(
                api_groups=["keda.sh"],
                resources=["scaledobjects"],
                verbs=["get", "list", "watch", "patch", "update"]
            )
        ]
    )
    
    try:
        rbac_v1.create_namespaced_role(namespace="cms", body=role)
        print("Created Role 'benchmark-role'")
    except client.exceptions.ApiException as e:
        if e.status == 409:  # Already exists
            # Replace the existing role
            rbac_v1.replace_namespaced_role(name="benchmark-role", namespace="cms", body=role)
            print("Updated Role 'benchmark-role'")
        else:
            raise
    
    # Create RoleBinding
    role_binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(
            name="benchmark-role-binding",
            namespace="cms"
        ),
        subjects=[
            client.V1Subject(
                kind="ServiceAccount",
                name="benchmark-sa",
                namespace="cms"
            )
        ],
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name="benchmark-role"
        )
    )
    
    try:
        rbac_v1.create_namespaced_role_binding(namespace="cms", body=role_binding)
        print("Created RoleBinding 'benchmark-role-binding'")
    except client.exceptions.ApiException as e:
        if e.status == 409:  # Already exists
            # Replace the existing role binding
            rbac_v1.replace_namespaced_role_binding(name="benchmark-role-binding", namespace="cms", body=role_binding)
            print("Updated RoleBinding 'benchmark-role-binding'")
        else:
            raise

if __name__ == "__main__":
    create_service_account() 