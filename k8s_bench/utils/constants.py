UPGRADE_SITE_SCRIPT = """
import glob
import json
import os
import shutil
import subprocess
from distutils.dir_util import copy_tree

import frappe
from frappe.installer import update_site_config
from frappe.migrate import migrate

FROM_BENCH_PATH = "FROM_BENCH_PATH"
SITE_NAME = "SITE_NAME"
MAINTENANCE_MODE = "maintenance_mode"
PAUSE_SCHEDULER = "pause_scheduler"
SITE_CONFIG_FILE = "site_config.json"
COMMON_SITE_CONFIG_FILE = "common_site_config.json"


def main():
	env = get_env()
	from_site_config_path = os.path.join(
		env.get(FROM_BENCH_PATH), env.get(SITE_NAME), SITE_CONFIG_FILE,
	)

	copy_site_stub_from_bench(
		env.get(FROM_BENCH_PATH), env.get(SITE_NAME),
	)

	try:
		migrate_site(env.get(SITE_NAME))

		# on successful migration, move skipped files
		copy_user_files(env.get(FROM_BENCH_PATH), env.get(SITE_NAME))

		# delete site_name from_bench_path
		delete_site_dir(os.path.join(env.get(FROM_BENCH_PATH), env.get(SITE_NAME),))

		unset_maintenance_mode(os.path.join(".", env.get(SITE_NAME), SITE_CONFIG_FILE))

		frappe.destroy()
	except Exception as exc:

		# if failed migration, retore from previous backup
		restore_previous_db(env)

		# delete site_name directory from new bench
		delete_site_dir(os.path.join(".", env.get(SITE_NAME),))

		# log error
		print(repr(exc))
		unset_maintenance_mode(
			os.path.join(env.get(FROM_BENCH_PATH), env.get(SITE_NAME), SITE_CONFIG_FILE,)
		)
		frappe.destroy()
		exit(1)


def get_env():
	env = {
		f"{FROM_BENCH_PATH}": os.environ.get(FROM_BENCH_PATH),
		f"{SITE_NAME}": os.environ.get(SITE_NAME),
	}

	if not env.get(FROM_BENCH_PATH):
		print(f"environment variable {FROM_BENCH_PATH} not set")
		exit(1)

	if not env.get(SITE_NAME):
		print(f"environment variable {SITE_NAME} not set")
		exit(1)

	return env


def set_maintenance_mode(site_config_path):
	print(f"Set Maintenance Mode for {site_config_path}")
	update_site_config(
		key=MAINTENANCE_MODE, value=1, site_config_path=site_config_path,
	)
	update_site_config(
		key=PAUSE_SCHEDULER, value=1, site_config_path=site_config_path,
	)


def unset_maintenance_mode(site_config_path):
	print(f"Unset Maintenance Mode for {site_config_path}")
	update_site_config(
		key=MAINTENANCE_MODE, value=0, site_config_path=site_config_path,
	)
	update_site_config(
		key=PAUSE_SCHEDULER, value=0, site_config_path=site_config_path,
	)


def copy_site_stub_from_bench(sites_path, site_name):
	print(f"Copy site stub from {sites_path} for {site_name}")
	if not os.path.exists(os.path.join(".", site_name)):
		os.makedirs(os.path.join(".", site_name))

	if not os.path.exists(os.path.join(".", site_name, SITE_CONFIG_FILE)):
		shutil.copy2(
			os.path.join(sites_path, site_name, SITE_CONFIG_FILE),
			os.path.join(".", site_name, SITE_CONFIG_FILE),
		)


def migrate_site(site):
	print("Migrating", site)
	frappe.init(site=site)
	frappe.connect()
	migrate()


def copy_user_files(from_bench_path, site_name):
	try:
		print("Copying private and public directories for site")
		copy_tree(
			os.path.join(from_bench_path, site_name, "private"),
			os.path.join(".", site_name, "private"),
		)
		copy_tree(
			os.path.join(from_bench_path, site_name, "public"),
			os.path.join(".", site_name, "public"),
		)
	except Exception as exc:
		print(repr(exc))
		exit(1)


def delete_site_dir(site_dir):
	try:
		print(f"Deleting {site_dir}")
		shutil.rmtree(site_dir)
	except Exception as exc:
		print(repr(exc))
		exit(1)


def restore_previous_db(env):
	print("Restoring old DB")
	versions = None
	latest_backup_gz = max(
		glob.iglob(
			os.path.join(
				env.get(FROM_BENCH_PATH),
				env.get(SITE_NAME),
				"private",
				"backups",
				"*-database.sql.gz",
			)
		),
		key=os.path.getctime,
	)
	latest_backup = latest_backup_gz.replace(".gz", "")

	config = get_config()
	site_config = get_site_config(env.get(SITE_NAME))

	db_host = site_config.get("db_host", config.get("db_host"))
	db_port = site_config.get("db_port", config.get("db_port", 3306))
	db_name = site_config.get("db_name")
	db_password = site_config.get("db_password")

	command = ["gunzip", "-c", latest_backup_gz]

	with open(latest_backup, "w") as db_file:
		print("Extract Database GZip for site {}".format(env.get(SITE_NAME)))
		run_command(command, stdout=db_file)

	mysql_command = [
		"mysql",
		f"-u{db_name}",
		f"-h{db_host}",
		f"-p{db_password}",
		f"-P{db_port}",
	]

	# drop db if exists for clean restore
	drop_database = mysql_command + ["-e", f"DROP DATABASE IF EXISTS `{db_name}`;"]
	run_command(drop_database)

	# create db
	create_database = mysql_command + ["-e", f"CREATE DATABASE IF NOT EXISTS `{db_name}`;"]
	run_command(create_database)

	print("Restoring MariaDB")
	with open(latest_backup, "r") as db_file:
		run_command(mysql_command + [f"{db_name}"], stdin=db_file)

	if os.path.isfile(latest_backup):
		os.remove(latest_backup)


def run_command(command, stdout=None, stdin=None, stderr=None):
	stdout = stdout or subprocess.PIPE
	stderr = stderr or subprocess.PIPE
	stdin = stdin or subprocess.PIPE
	process = subprocess.Popen(command, stdout=stdout, stdin=stdin, stderr=stderr)
	out, error = process.communicate()
	if process.returncode:
		print("Something went wrong:")
		print(f"return code: {process.returncode}")
		print(f"stdout:\n{out}")
		print(f"\nstderr:\n{error}")
		exit(process.returncode)


def get_config():
	config = None
	try:
		with open(COMMON_SITE_CONFIG_FILE) as config_file:
			config = json.load(config_file)
	except FileNotFoundError as exception:
		print(exception)
		exit(1)
	except Exception:
		print(COMMON_SITE_CONFIG_FILE + " is not valid")
		exit(1)
	return config


def get_site_config(site_name):
	site_config = None
	with open(f"{site_name}/{SITE_CONFIG_FILE}") as site_config_file:
		site_config = json.load(site_config_file)
	return site_config


if __name__ == "__main__":
	main()
"""

SITES_DIR = "sites-dir"
BASE_SITES_DIR = "base-sites-dir"

UPGRADE_SITE = "upgrade-site"
ASSETS_CACHE = "assets-cache"
