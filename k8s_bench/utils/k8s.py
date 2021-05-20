import frappe
import json
from k8s_bench.utils.constants import (
    ASSETS_CACHE,
    BASE_SITES_DIR,
    SITES_DIR,
    UPGRADE_SITE,
    UPGRADE_SITE_SCRIPT,
)
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import datetime


def to_dict(obj):
    if hasattr(obj, "attribute_map"):
        result = {}
        for k, v in getattr(obj, "attribute_map").items():
            val = getattr(obj, k)
            if val is not None:
                result[v] = to_dict(val)
        return result
    elif type(obj) == list:
        return [to_dict(x) for x in obj]
    elif type(obj) == datetime:
        return str(obj)
    else:
        return obj


def load_config():
    if frappe.get_conf().get("developer_mode"):
        config.load_kube_config()
    else:
        config.load_incluster_config()


def create_upgrade_job(site_name, base_pvc_name):
    not_set = "NOT_SET"

    if not site_name or not base_pvc_name:
        frappe.local.response["http_status_code"] = 400
        return {
            "site_name": site_name or not_set,
            "base_pvc_name": base_pvc_name or not_set,
        }

    k8s_settings = frappe.get_single("K8s Bench Settings")

    if (
        not k8s_settings.namespace
        or not k8s_settings.nginx_image
        or not k8s_settings.python_image
        or not k8s_settings.pvc_name
    ):
        out = {
            "namespace": k8s_settings.namespace or not_set,
            "nginx_image": k8s_settings.nginx_image or not_set,
            "python_image": k8s_settings.python_image or not_set,
            "pvc_name": k8s_settings.pvc_name or not_set,
        }
        frappe.local.response["http_status_code"] = 501
        return out

    job_name = f"{UPGRADE_SITE}-{site_name}"
    load_config()

    batch_v1_api = client.BatchV1Api()

    body = client.V1Job(api_version="batch/v1", kind="Job")
    body.metadata = client.V1ObjectMeta(namespace=k8s_settings.namespace, name=job_name)
    body.status = client.V1JobStatus()
    body.spec = client.V1JobSpec(
        template=client.V1PodTemplateSpec(
            spec=client.V1PodSpec(
                init_containers=[
                    client.V1Container(
                        name="populate-assets",
                        image=k8s_settings.nginx_image,
                        command=["/bin/bash", "-c"],
                        args=["rsync -a --delete /var/www/html/assets/frappe /assets"],
                        volume_mounts=[
                            client.V1VolumeMount(
                                name="assets-cache", mount_path="/assets"
                            ),
                        ],
                    )
                ],
                security_context=client.V1PodSecurityContext(
                    supplemental_groups=[1000]
                ),
                containers=[
                    client.V1Container(
                        name="upgrade-site",
                        image=k8s_settings.python_image,
                        command=["/home/frappe/frappe-bench/env/bin/python"],
                        args=["/home/frappe/frappe-bench/commands/upgrade_site.py"],
                        volume_mounts=[
                            client.V1VolumeMount(
                                name=SITES_DIR,
                                mount_path="/home/frappe/frappe-bench/sites",
                            ),
                            client.V1VolumeMount(
                                name=BASE_SITES_DIR, mount_path="/opt/base-sites"
                            ),
                            client.V1VolumeMount(
                                name=UPGRADE_SITE,
                                mount_path="/home/frappe/frappe-bench/commands",
                            ),
                            client.V1VolumeMount(
                                name=ASSETS_CACHE, mount_path="/assets"
                            ),
                        ],
                        env=[
                            client.V1EnvVar(name="SITE_NAME", value=site_name),
                            client.V1EnvVar(
                                name="FROM_BENCH_PATH", value="/opt/base-sites"
                            ),
                        ],
                    )
                ],
                restart_policy="Never",
                volumes=[
                    client.V1Volume(
                        name=SITES_DIR,
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=k8s_settings.pvc_name, read_only=False
                        ),
                    ),
                    client.V1Volume(
                        name=BASE_SITES_DIR,
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=base_pvc_name,
                            read_only=False,
                        ),
                    ),
                    client.V1Volume(
                        name=UPGRADE_SITE,
                        config_map=client.V1ConfigMapVolumeSource(name=UPGRADE_SITE),
                    ),
                    client.V1Volume(
                        name=ASSETS_CACHE, empty_dir=client.V1EmptyDirVolumeSource()
                    ),
                ],
            )
        )
    )

    try:
        api_response = batch_v1_api.create_namespaced_job(
            k8s_settings.namespace, body, pretty=True
        )
        return job_name + " created"
    except (ApiException, Exception) as e:
        status_code = getattr(e, "status", 500)
        out = {
            "error": e,
            "params": {"site_name": site_name, "base_pvc_name": base_pvc_name},
        }
        reason = getattr(e, "reason")
        if reason:
            out["reason"] = reason

        frappe.log_error(out, "Exception: BatchV1Api->create_namespaced_job")
        frappe.local.response["http_status_code"] = status_code
        return out


def create_site_ingress(site_name):
    k8s_settings = frappe.get_single("K8s Bench Settings")

    if (
        not k8s_settings.namespace
        or not k8s_settings.wildcard_domain
        or not k8s_settings.wildcard_tls_secret_name
        or not k8s_settings.cert_manager_cluster_issuer
    ):
        not_set = "NOT_SET"
        out = {
            "namespace": k8s_settings.namespace or not_set,
            "wildcard_domain": k8s_settings.wildcard_domain or not_set,
            "wildcard_tls_secret_name": k8s_settings.wildcard_tls_secret_name
            or not_set,
            "cert_manager_cluster_issuer": k8s_settings.cert_manager_cluster_issuer
            or not_set,
        }
        frappe.local.response["http_status_code"] = 501
        return out

    load_config()
    networking_v1_api = client.NetworkingV1beta1Api()

    body = client.NetworkingV1beta1Ingress()

    body.metadata = client.V1ObjectMeta(
        namespace=k8s_settings.namespace,
        name=site_name,
        annotations={
            "cert-manager.io/cluster-issuer": k8s_settings.cert_manager_cluster_issuer
        },
    )
    body.status = client.V1JobStatus()

    body.spec = client.NetworkingV1beta1IngressSpec(
        rules=[
            client.NetworkingV1beta1IngressRule(
                host=site_name,
                http=client.NetworkingV1beta1HTTPIngressRuleValue(
                    paths=[
                        client.NetworkingV1beta1HTTPIngressPath(
                            backend=client.NetworkingV1beta1IngressBackend(
                                service_name=k8s_settings.service_name, service_port=80
                            )
                        )
                    ]
                ),
            ),
        ],
        tls=[
            client.NetworkingV1beta1IngressTLS(
                hosts=[f"*.{k8s_settings.wildcard_domain}"],
                secret_name=k8s_settings.wildcard_tls_secret_name,
            ),
        ],
    )

    try:
        ingress = networking_v1_api.create_namespaced_ingress(
            k8s_settings.namespace, body
        )
        return to_dict(ingress)
    except (ApiException, Exception) as e:
        status_code = getattr(e, "status", 500)
        out = {"error": e, "params": {"site_name": site_name}}
        reason = getattr(e, "reason")
        if reason:
            out["reason"] = reason
        frappe.log_error(
            out, "Exception: NetworkingV1beta1Api->create_namespaced_ingress"
        )
        frappe.local.response["http_status_code"] = status_code
        return out


def patch_ingress(site_name):
    k8s_settings = frappe.get_single("K8s Bench Settings")
    not_set = "NOT_SET"
    if not k8s_settings.service_name or not k8s_settings.namespace:
        frappe.local.response["http_status_code"] = 501
        return {
            "namespace": k8s_settings.namespace or not_set,
            "service_name": k8s_settings.service_name or not_set,
        }

    load_config()
    networking_v1_api = client.NetworkingV1beta1Api()

    try:
        body = networking_v1_api.read_namespaced_ingress(
            site_name, k8s_settings.namespace
        )
        if len(body.spec.rules) > 0:
            if len(body.spec.rules[0].http.paths) > 0:
                body.spec.rules[0].http.paths[
                    0
                ].backend.service_name = k8s_settings.service_name

            networking_v1_api.patch_namespaced_ingress(
                site_name, k8s_settings.namespace, body
            )

        return to_dict(body)
    except (ApiException, Exception) as e:
        status_code = getattr(e, "status", 500)
        out = {"error": e, "params": {"site_name": site_name}}
        reason = getattr(e, "reason")
        if reason:
            out["reason"] = reason
        frappe.log_error(out, "Exception: NetworkingV1beta1Api - patch_ingress")
        frappe.local.response["http_status_code"] = status_code
        return out


def delete_site_resources(site_name):
    not_set = "NOT_SET"
    k8s_settings = frappe.get_single("K8s Bench Settings")
    if not k8s_settings.namespace:
        frappe.local.response["http_status_code"] = 501
        return {
            "namespace": k8s_settings.namespace or not_set,
        }

    load_config()
    networking_v1_api = client.NetworkingV1beta1Api()
    res = {"status": "Accepted"}
    try:
        ing = networking_v1_api.delete_namespaced_ingress(
            site_name, k8s_settings.namespace
        )
        res["ingress_deleted"] = to_dict(ing)
    except Exception as e:
        out = {"error": e, "params": {"site_name": site_name}}
        reason = getattr(e, "reason")
        if reason:
            out["reason"] = reason
        res["ingress_delete_error"] = out
        frappe.log_error(
            out,
            "Exception: delete_site_resources - NetworkingV1beta1Api->delete_namespaced_ingress",
        )

    batch_v1_api = client.BatchV1Api()

    try:
        job = batch_v1_api.delete_namespaced_job(
            f"{UPGRADE_SITE}-{site_name}", k8s_settings.namespace
        )
        res["upgrade_job_deleted"] = to_dict(job)
    except (ApiException, Exception) as e:
        out = {"error": e, "params": {"site_name": site_name}}
        reason = getattr(e, "reason")
        if reason:
            out["reason"] = reason
        res["job_delete_error"] = out
        frappe.log_error(
            out, "Exception: delete_site_resources - BatchV1Api->delete_namespaced_job"
        )

    return res


def get_job_status(job_name):
    not_set = "NOT_SET"
    k8s_settings = frappe.get_single("K8s Bench Settings")
    if not k8s_settings.namespace:
        frappe.local.response["http_status_code"] = 501
        return {
            "namespace": k8s_settings.namespace or not_set,
        }

    load_config()
    batch_v1_api = client.BatchV1Api()
    try:
        job = batch_v1_api.read_namespaced_job_status(job_name, k8s_settings.namespace)
        return to_dict(job)
    except (ApiException, Exception) as e:
        status_code = getattr(e, "status", 500)
        out = {
            "error": e,
            "params": {"job_name": job_name, "namespace": k8s_settings.namespace},
        }
        reason = getattr(e, "reason")
        if reason:
            out["reason"] = reason
        frappe.log_error(out, "Exception: BatchV1Api->read_namespaced_job_status")
        frappe.local.response["http_status_code"] = status_code
        return out


def read_ingress(site_name):
    not_set = "NOT_SET"
    k8s_settings = frappe.get_single("K8s Bench Settings")
    if not k8s_settings.namespace:
        frappe.local.response["http_status_code"] = 501
        return {
            "namespace": k8s_settings.namespace or not_set,
        }

    load_config()
    networking_v1_api = client.NetworkingV1beta1Api()
    try:
        ingress = networking_v1_api.read_namespaced_ingress(
            site_name, k8s_settings.namespace
        )
        return to_dict(ingress)
    except (ApiException, Exception) as e:
        status_code = getattr(e, "status", 500)
        out = {
            "error": e,
            "params": {"site_name": site_name, "namespace": k8s_settings.namespace},
        }

        reason = getattr(e, "reason")
        if reason:
            out["reason"] = reason

        frappe.log_error(
            out, "Exception: NetworkingV1beta1Api->read_namespaced_ingress"
        )
        frappe.local.response["http_status_code"] = status_code
        return out
