import frappe

from k8s_bench.utils.constants import UPGRADE_SITE
from k8s_bench.utils.k8s import (
    create_upgrade_job,
    create_site_ingress,
    patch_ingress,
    delete_site_resources,
    get_job_status,
    read_ingress,
)


@frappe.whitelist(methods=["POST"])
def upgrade_site(site_name, base_pvc_name):
    return create_upgrade_job(site_name, base_pvc_name)


@frappe.whitelist(methods=["POST"])
def create_ingress(site_name):
    return create_site_ingress(site_name)


@frappe.whitelist(methods=["POST"])
def change_ingress_service_to_current_bench(site_name):
    return patch_ingress(site_name)


@frappe.whitelist(methods=["POST"])
def delete_resources(site_name):
    return delete_site_resources(site_name)


@frappe.whitelist(methods=["GET"])
def job_status(job_name):
    return get_job_status(job_name)


@frappe.whitelist(methods=["GET"])
def get_ingress(site_name):
    return read_ingress(site_name)

