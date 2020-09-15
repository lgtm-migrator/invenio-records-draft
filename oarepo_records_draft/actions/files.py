import six
from invenio_base.utils import obj_or_import_string
from werkzeug.utils import import_string

try:

    from functools import wraps, lru_cache

    from flask import jsonify, abort
    from flask import request
    from flask.views import MethodView
    from invenio_db import db
    from invenio_records_rest.utils import deny_all
    from invenio_records_rest.views import pass_record
    from invenio_rest import ContentNegotiatedMethodView

    from invenio_files_rest.signals import file_uploaded, file_downloaded, file_deleted
    from invenio_files_rest.serializer import json_serializer

    from oarepo_records_draft.signals import attachment_uploaded, attachment_deleted, attachment_downloaded


    @lru_cache(maxsize=32)
    def apply_permission(perm_or_factory):
        if isinstance(perm_or_factory, six.string_types):
            perm_or_factory = import_string(perm_or_factory)

        def func(*args, **kwargs):
            if callable(perm_or_factory):
                return perm_or_factory(*args, **kwargs)
            return perm_or_factory

        return func


    # adopted from invenio-records-rest
    def verify_file_permission(permission_factory, record, key, missing_ok):
        if key not in record.files and not missing_ok:
            abort(404)

        try:
            file_object = record.files[key]
        except KeyError:
            file_object = None

        permission = apply_permission(permission_factory)(record=record, key=key, file_object=file_object)

        if not permission.can():
            from flask_login import current_user
            if not current_user.is_authenticated:
                abort(401)
            abort(403)


    def need_file_permission(factory_name, missing_ok=False):
        def permission_builder(f):
            @wraps(f)
            def permission_decorator(self, record=None, *args, **kwargs):
                permission_factory = getattr(self, factory_name, deny_all)

                # FIXME use context instead
                request._methodview = self

                key = kwargs['key']
                verify_file_permission(permission_factory, record, key, missing_ok)

                return f(self, record=record, *args, **kwargs)

            return permission_decorator

        return permission_builder


    class FileResource(MethodView):
        view_name = '{0}_attachment'

        def __init__(self, get_file_factory=None, put_file_factory=None, delete_file_factory=None,
                     restricted=True, as_attachment=True, *args, **kwargs):
            super().__init__(
                *args,
                **kwargs
            )
            self.put_file_factory = put_file_factory
            self.get_file_factory = get_file_factory
            self.delete_file_factory = delete_file_factory
            self.restricted = restricted
            self.as_attachment = as_attachment

        @pass_record
        @need_file_permission('put_file_factory', missing_ok=True)
        def put(self, pid, record, key):
            record.files[key] = request.stream
            record.commit()
            db.session.commit()
            ret = jsonify(record.files[key].dumps())
            version = record.files[key].get_version()
            file_uploaded.send(version)
            attachment_uploaded.send(version, record=record, file=record.files[key])
            ret.status_code = 201
            return ret

        @pass_record
        @need_file_permission('delete_file_factory')
        def delete(self, pid, record, key):
            deleted_record = record.files[key]
            deleted_record_version = deleted_record.get_version()
            del record.files[key]
            record.commit()
            db.session.commit()
            file_deleted.send(deleted_record_version)
            attachment_deleted.send(deleted_record_version, record=record, file=deleted_record)
            ret = jsonify(deleted_record.dumps())
            ret.status_code = 200
            return ret

        @pass_record
        @need_file_permission('get_file_factory')
        def get(self, pid, record, key):
            obj = record.files[key]
            obj = obj.get_version()
            file_downloaded.send(obj)
            attachment_downloaded.send(obj, record=record, file=record.files[key])
            return obj.send_file(restricted=self.call(self.restricted, record, obj, key),
                                 as_attachment=self.call(self.as_attachment, record, obj, key))

        def call(self, prop, record, obj, key):
            if callable(prop):
                return prop(record=record, obj=obj, key=key)
            return prop


    class FileListResource(ContentNegotiatedMethodView):

        view_name = '{0}_attachments'

        def __init__(self, get_file_factory=None, serializers=None, *args, **kwargs):
            super().__init__(
                *args,
                serializers=serializers or {
                    'application/json': json_serializer,
                },
                default_media_type='application/json',
                **kwargs
            )
            self.get_file_factory = get_file_factory

        @pass_record
        def get(self, pid, record):
            return jsonify([
                file for key, file in record.files.filesmap.items()
                if apply_permission(self.get_file_factory)(record=record, key=key, file_object=file).can()
            ])

except:
    FileResource = None
    FileListResource = None

__all__ = ('FileResource', 'FileListResource')
