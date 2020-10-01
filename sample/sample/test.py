from io import BytesIO

from flask import jsonify
from flask.views import MethodView
from invenio_records_rest.views import pass_record


def uploader(record, key, files, pid, request, resolver, endpoint, **kwargs):
    if key == 'test-uploader':
        bt = BytesIO(b'blah')
        files[key] = bt
        return lambda: ({
            'test-uploader': True,
            'url': resolver(TestResource.view_name)
        })


class TestResource(MethodView):
    view_name = '{endpoint}_test'

    @pass_record
    def get(self, pid, record):
        return jsonify({'status': 'ok'})


def extras(code, files, rest_endpoint, extra):
    return {
        'files/_test': TestResource.as_view(
            TestResource.view_name.format(endpoint=code)
        )
    }
