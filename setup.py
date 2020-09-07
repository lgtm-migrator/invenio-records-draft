# -*- coding: utf-8 -*-
"""Setup module for flask taxonomy."""
import os
from os import path

from setuptools import setup

install_requires = [
    'wrapt>=1.11.2',
    'oarepo_validate',
    'deepmerge'
]

tests_require = [
    'oarepo[tests]',
    'pytest-cov'
]

extras_require = {
    'tests': tests_require,
}

setup_requires = [
    'pytest-runner>=2.7',
]

g = {}
with open(os.path.join('oarepo_records_draft', 'version.py'), 'rt') as fp:
    exec(fp.read(), g)
    version = g['__version__']

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="oarepo-records-draft",
    version=version,
    url="https://github.com/oarepo/oarepo-records-draft",
    license="MIT",
    author="Mirek Šimek",
    author_email="miroslav.simek@vscht.cz",
    description="Handling Draft and Production invenio records in one package",
    zip_safe=False,
    packages=['oarepo_records_draft'],
    entry_points={
        # 'flask.commands': [
        #     'draft = oarepo_records_draft.cli:draft',
        # ],
        'invenio_config.module': [
            'oarepo_records_draft = oarepo_records_draft.config',
        ],
        'invenio_base.api_apps': [
            'oarepo_records_draft = oarepo_records_draft.ext:RecordsDraft',
        ],
        'invenio_base.apps': [
            'oarepo_records_draft = oarepo_records_draft.ext:RecordsDraft',
        ],
    },
    include_package_data=True,
    setup_requires=setup_requires,
    extras_require=extras_require,
    install_requires=install_requires,
    tests_require=tests_require,
    long_description=long_description,
    long_description_content_type='text/markdown',
    platforms='any',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Development Status :: 4 - Beta',
    ],
)
