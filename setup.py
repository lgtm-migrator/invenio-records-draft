# -*- coding: utf-8 -*-
"""Setup module for flask taxonomy."""
import os
from os import path

from setuptools import setup
    
OAREPO_VERSION = os.environ.get('OAREPO_VERSION', '3.1.1')

install_requires = [
    'wrapt>=1.11.2'
]

deploy_requires = [
    'oarepo[deploy]~={version}'.format(version=OAREPO_VERSION),
]

tests_require = [
    'oarepo[tests]~={version}'.format(version=OAREPO_VERSION),
    'sqlalchemy-continuum'
]

extras_require = {
    'tests': tests_require,
    'tests-es7': {
        'oarepo[tests-es7]~={version}'.format(version=OAREPO_VERSION),
    },
    'devel': tests_require,
    'deploy': deploy_requires,
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
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Development Status :: 4 - Beta',
    ],
)
