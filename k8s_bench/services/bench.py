import time
from subprocess import check_output

import frappe
from bench_manager.bench_manager.doctype.site.site import (
    create_site as _create_site,
)
from bench_manager.bench_manager.utils import (
    safe_decode,
    verify_whitelisted_call,
)
from k8s_bench.utils.setup import setup_bench as _setup_bench


@frappe.whitelist()
def create_site(site_name, key, apps=None):
    mysql_password = frappe.get_conf().get("root_password")
    admin_password = frappe.get_conf().get("admin_password")

    verify_whitelisted_call()
    commands = [
        "bench new-site --mariadb-root-password {mysql_password} --admin-password {admin_password} --no-mariadb-socket {site_name}".format(
            site_name=site_name,
            admin_password=admin_password,
            mysql_password=mysql_password,
        ),
        f"bench --site {site_name} add-system-manager --first-name {first_name} --last-name {last_name} --password {password} {email}"
    ]

    list_apps = ["frappe"]

    if apps:
        list_apps = apps.split(",")
        for app in list_apps:
            commands.append(f"bench --site {site_name} install-app {app}")

    frappe.enqueue(
        "bench_manager.bench_manager.utils.run_command",
        commands=commands,
        doctype="Bench Settings",
        key=key,
    )
    return f"Creating {site_name}"


@frappe.whitelist()
def drop_site(site_name, key):
    if not frappe.has_permission("Bench Settings"):
        frappe.local.response["http_status_code"] = 403
        return "Not Permitted"

    archived_sites_path = "archived_sites"
    commands = [
        f"bench drop-site {site_name} --no-backup --archived-sites-path {archived_sites_path}"
    ]

    frappe.enqueue(
        "bench_manager.bench_manager.utils.run_command",
        commands=commands,
        doctype="Site",
        key=key,
        docname=site_name,
    )
    return f"Deleting {site_name}"


@frappe.whitelist(methods=["POST"])
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
    k8s_settings = _setup_bench(
        namespace,
        nginx_image,
        python_image,
        cluster_issuer,
        pvc_name,
        service_name,
        wildcard_domain,
        wildcard_tls_secret_name,
    )
    return k8s_settings.as_dict()
