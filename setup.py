# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in k8s_bench/__init__.py
from k8s_bench import __version__ as version

setup(
    name="k8s_bench",
    version=version,
    description="Bench Manager Kubernetes API",
    author="Castlecraft Ecommerce Pvt Ltd",
    author_email="support@castlecraft.in",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
