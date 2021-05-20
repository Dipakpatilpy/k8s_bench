import frappe


def setup_bench(
    namespace=None,
    nginx_image=None,
    python_image=None,
    cluster_issuer=None,
    pvc_name=None,
    service_name=None,
    wildcard_domain=None,
    wildcard_tls_secret_name=None,
):
    k8s_settings = frappe.get_single("K8s Bench Settings")

    if namespace:
        k8s_settings.namespace = namespace
    if nginx_image:
        k8s_settings.nginx_image = nginx_image
    if python_image:
        k8s_settings.python_image = python_image
    if cluster_issuer:
        k8s_settings.cert_manager_cluster_issuer = cluster_issuer
    if pvc_name:
        k8s_settings.pvc_name = pvc_name
    if service_name:
        k8s_settings.service_name = service_name
    if wildcard_domain:
        k8s_settings.wildcard_domain = wildcard_domain
    if wildcard_tls_secret_name:
        k8s_settings.wildcard_tls_secret_name = wildcard_tls_secret_name

    k8s_settings.save()
    return k8s_settings
