# -*- coding: utf-8 -*-
"""Setup module for flask taxonomy."""
import os

from setuptools import setup

readme = open('README.rst').read()

INVENIO_VERSION = "3.1.1"

install_requires = [
    'invenio[base,metadata]~={version}'.format(version=INVENIO_VERSION),
    'wrapt>=1.11.2'
]

tests_require = [
    'pytest>=4.6.3',
    # 'factory-boy>=2.12.0',
    # 'pdbpp>=0.10.0',
    'pydocstyle>=1.0.0,<4.0.0',
    'check-manifest>=0.25',
    'coverage>=4.0',
    'isort>=4.3.3',
    # 'mock>=2.0.0',
    'pytest-cache>=1.0',
    'pytest-invenio>=1.0.2,<1.1.0',
    'pytest-mock>=1.6.0',
    'pytest-cov>=1.8.0',
    'pytest-random-order>=0.5.4',
    'pytest-pep8>=1.0.6',
]

extras_require = {
    'tests': tests_require,
}

setup_requires = [
    'pytest-runner>=2.7',
]

g = {}
with open(os.path.join('invenio_records_draft', 'version.py'), 'rt') as fp:
    exec(fp.read(), g)
    version = g['__version__']

setup(
    name="invenio-records-draft",
    version=version,
    url="https://github.com/oarepo/invenio-records-draft",
    license="MIT",
    author="Mirek Šimek",
    author_email="miroslav.simek@vscht.cz",
    description="Handling Draft and Production invenio records in one package",
    zip_safe=False,
    packages=['invenio_records_draft'],
    entry_points={
    },
    include_package_data=True,
    setup_requires=setup_requires,
    extras_require=extras_require,
        install_requires=install_requires,
    tests_require=tests_require,
    platforms='any',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Development Status :: 4 - Beta',
    ],
)
