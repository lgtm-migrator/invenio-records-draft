import os

from setuptools import find_packages, setup

packages = find_packages()

setup(
    name='sample',
    version='1.0.0',
    description=__doc__,
    long_description='Sample app',
    keywords='Sample app',
    license='MIT',
    author='Mirek Simek',
    author_email='miroslav.simek@vscht.cz',
    url='https://github.com/oarepo/invenio-records-draft',
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    entry_points={
        'invenio_base.apps': [
            'records = sample.records:Records',
        ],
        'invenio_base.blueprints': [
            'records = sample.theme.views:blueprint',
            'records_records = sample.records.views:blueprint',
        ],
        'invenio_assets.webpack': [
            'sample_theme = sample.theme.webpack:theme',
        ],
        'invenio_config.module': [
            'sample = sample.config',
            'records = sample.records.config',
        ],
        'invenio_i18n.translations': [
            'messages = sample',
        ],
        'invenio_base.api_apps': [
            'sample = sample.records:Records',
         ],
        'invenio_jsonschemas.schemas': [
            'sample = sample.records.jsonschemas'
        ],
        'invenio_search.mappings': [
            'records = sample.records.mappings'
        ],
    },
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Development Status :: 3 - Alpha',
    ],
)
