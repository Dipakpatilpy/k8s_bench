import click
import frappe
from frappe.commands import get_site, pass_context
from k8s_bench.utils.setup import setup_bench


@click.command("k8s-setup", help="Setup kubernetes resources")
@click.option("--namespace", help="Namespace in which ERPNext will be installed")
@click.option("--nginx-image", help="Nginx Image used by apps")
@click.option(
    "--python-image",
    help="Python Image used by apps",
)
@click.option("--cluster-issuer", help="cert-manager.io Cluster Issuer")
@click.option("--pvc-name", help="PVC name of sites directory")
@click.option("--service-name", help="Service Name where ERPNext is stored")
@click.option("--wildcard-domain", help="Base domain for the bench sites")
@click.option(
    "--wildcard-tls-secret-name",
    help="K8s secret for wildcard certificate",
)
@pass_context
def k8s_setup(
    context,
    namespace,
    nginx_image,
    python_image,
    cluster_issuer,
    pvc_name,
    service_name,
    wildcard_domain,
    wildcard_tls_secret_name,
):
    click.secho("Updating K8s Bench Settings ...", bold=True)
    click.secho(
        f"""
\033[1m
Env Vars                        Values
\033[0m
namespace                       {namespace}
nginx_image                     {nginx_image}
python_image                    {python_image}
cluster_issuer                  {cluster_issuer}
pvc_name                        {pvc_name}
service_name                    {service_name}
wildcard_domain                 {wildcard_domain}
wildcard_tls_secret_name        {wildcard_tls_secret_name}
	""",
        underline=True,
    )
    site = get_site(context)
    frappe.init(site=site)
    frappe.connect(site=site)
    k8s_settings = setup_bench(
        namespace,
        nginx_image,
        python_image,
        cluster_issuer,
        pvc_name,
        service_name,
        wildcard_domain,
        wildcard_tls_secret_name,
    )
    frappe.db.commit()
    frappe.destroy()
