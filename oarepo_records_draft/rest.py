from invenio_records_rest.facets import terms_filter


def term_facet(field, order='desc', size=100):
    return {
        'terms': {
            'field': field,
            'size': size,
            "order": {"_count": order}
        },
    }


DRAFT_FACETS = {
    'draftValid': term_facet('oarepo:validity.valid'),
    'draftMarshmallowErrorField': term_facet('oarepo:validity.errors.marshmallow.field'),
    'draftMarshmallowErrorMessage': term_facet('oarepo:validity.errors.marshmallow.message.raw'),
    'draftSchemaErrorField': term_facet('oarepo:validity.errors.schema.field'),
    'draftSchemaErrorMessage': term_facet('oarepo:validity.errors.schema.message.raw'),
    'draftOtherErrorMessage': term_facet('oarepo:validity.errors.other.message.raw'),
    'draftAllErrorField': term_facet('oarepo:validity.errors.all.field'),
    'draftAllErrorMessage': term_facet('oarepo:validity.errors.all.message.raw'),
}

DRAFT_FILTERS = {
    'draftValid': terms_filter('oarepo:validity.valid'),
    'draftMarshmallowErrorField': terms_filter('oarepo:validity.errors.marshmallow.field'),
    'draftMarshmallowErrorMessage': terms_filter('oarepo:validity.errors.marshmallow.message.raw'),
    'draftSchemaErrorField': terms_filter('oarepo:validity.errors.schema.field'),
    'draftSchemaErrorMessage': terms_filter('oarepo:validity.errors.schema.message.raw'),
    'draftOtherErrorMessage': terms_filter('oarepo:validity.errors.other.message.raw'),
    'draftAllErrorField': terms_filter('oarepo:validity.errors.all.field'),
    'draftAllErrorMessage': terms_filter('oarepo:validity.errors.all.message.raw'),
}
