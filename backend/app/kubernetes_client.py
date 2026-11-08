from kubernetes import client, config


def load_kubernetes_config():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


load_kubernetes_config()

apps_v1 = client.AppsV1Api()
core_v1 = client.CoreV1Api()
autoscaling_v2 = client.AutoscalingV2Api()