# -*- coding: utf-8 -*-

import setuptools
import versioneer
import os

try:
    import pcbnew
except ImportError:
    if os.name == "nt":
        raise RuntimeError("No Pcbnew Python module found.\n" +
                           "Please make sure that you use KiCAD command prompt," +
                           "not the standard Command Prompt.")
    else:
        raise RuntimeError("No Pcbnew Python module found for the current Python interpreter.\n" +
                           "First, make sure that KiCAD is actually installed\n." +
                           "Then, make sure that you use the same Python interpreter as KiCAD uses.")



with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Prusaman",
    python_requires='>=3.7',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="Jan Mrázek",
    author_email="email@honzamrazek.cz",
    description="Automation for Prusa PCB export",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/prusa3d/KiKIt_fab_prusa",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "kikit",
        "click>=7.1",
        "ruamel.yaml==0.17.*",
        "python-tsp==0.2.*",
    ],
    setup_requires=[
        "versioneer"
    ],
    extras_require={
        "dev": ["pytest", "astunparse"],
    },
    zip_safe=False,
    include_package_data=True,
    entry_points = {
        "console_scripts": [
            "prusaman=prusaman.ui:cli",
        ],
    }
)
