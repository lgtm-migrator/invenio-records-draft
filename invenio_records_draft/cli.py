import click
from flask import current_app
from flask.cli import with_appcontext

from invenio_records_draft.proxies import current_drafts


@click.group()
def draft():
    """Draft commands."""


@draft.command('make-schemas')
@with_appcontext
def make_schemas():
    if 'INVENIO_RECORD_DRAFT_SCHEMAS' not in current_app.config:    # pragma: no cover
        print('Please set up INVENIO_RECORD_DRAFT_SCHEMAS in the configuration')
        return

    schemas = set()

    for cfg in current_app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
        published_schema = cfg['published_schema']
        draft_schema = cfg['draft_schema']
        if published_schema in schemas:
            continue        # pragma: no cover
        schemas.add(published_schema)
        output_path = current_drafts.make_draft_schema(published_schema, draft_schema)
        print('Created schema', output_path)


@draft.command('make-mappings')
@with_appcontext
def make_mappings():
    if 'INVENIO_RECORD_DRAFT_SCHEMAS' not in current_app.config:    # pragma: no cover
        print('Please set up INVENIO_RECORD_DRAFT_SCHEMAS in the configuration')
        return

    schemas = set()

    for cfg in current_app.config['INVENIO_RECORD_DRAFT_SCHEMAS']:
        published_schema = cfg['published_schema']
        draft_schema = cfg['draft_schema']
        if published_schema in schemas:
            continue        # pragma: no cover
        schemas.add(published_schema)
        output_path = current_drafts.make_draft_mapping(published_schema, draft_schema)
        print('Created mapping', output_path)
