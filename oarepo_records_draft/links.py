from functools import cached_property

from flask import url_for
from invenio_base.utils import obj_or_import_string
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from werkzeug.routing import BuildError

from oarepo_records_draft.types import RecordEndpointConfiguration

DEFAULT_LINKS_FACTORY = 'invenio_records_rest.links.default_links_factory'


class LinksFactory:
    def __init__(self, endpoint: RecordEndpointConfiguration, links_factory, actions=None):
        self.endpoint = endpoint
        self._links_factory = links_factory or DEFAULT_LINKS_FACTORY
        self.actions = actions

    @cached_property
    def links_factory(self):
        return obj_or_import_string(self._links_factory)

    def get_other_end_link(self, pid):
        try:
            other_end = self.endpoint.paired_endpoint
            # check if other side pid exists
            other_side_pid = PersistentIdentifier.get(other_end.pid_type, pid.pid_value)
            if other_side_pid.status != PIDStatus.DELETED:
                endpoint = 'invenio_records_rest.{0}_item'.format(other_end.rest_name)
                return url_for(endpoint, pid_value=pid.pid_value, _external=True)
        except PIDDoesNotExistError:
            pass
        return None

    def get_extra_url_rules(self, pid):
        resp = {}
        for rule, action in self.actions.items():
            try:
                if action.view_name:
                    resp[rule] = url_for(
                        'oarepo_records_draft.{0}'.format(
                            action.view_name.format(self.endpoint.rest_name)
                        ), pid_value=pid.pid_value, _external=True)
                else:
                    resp[rule] = url_for(
                        'oarepo_records_draft.{0}_{1}'.format(
                            rule,
                            self.endpoint.rest_name
                        ), pid_value=pid.pid_value, _external=True)
            except BuildError:
                pass
        return resp


class DraftLinksFactory(LinksFactory):
    def __call__(self, pid, record=None, **kwargs):
        resp = self.links_factory(pid, record=record, **kwargs)
        other_end = self.get_other_end_link(pid)
        if other_end:
            resp['published'] = other_end

        if record and self.endpoint.resolve('publish_permission_factory')(record=record).can():
            resp['publish'] = url_for(
                'oarepo_records_draft.publish_{0}'.format(self.endpoint.rest_name),
                pid_value=pid.pid_value, _external=True
            )
        resp.update(self.get_extra_url_rules(pid))
        return resp


class PublishedLinksFactory(LinksFactory):
    def __call__(self, pid, record=None, **kwargs):
        resp = self.links_factory(pid, record=record, **kwargs)
        other_end = self.get_other_end_link(pid)
        if other_end and self.endpoint.resolve('edit_permission_factory')(record=record).can():
            resp['draft'] = other_end

        if record and self.endpoint.resolve('unpublish_permission_factory')(record=record).can():
            resp['unpublish'] = url_for(
                'oarepo_records_draft.unpublish_{0}'.format(self.endpoint.rest_name),
                pid_value=pid.pid_value,
                _external=True
            )

        if record and self.endpoint.resolve('edit_permission_factory')(record=record).can():
            resp['edit'] = url_for(
                'oarepo_records_draft.edit_{0}'.format(self.endpoint.rest_name),
                pid_value=pid.pid_value,
                _external=True
            )

        resp.update(self.get_extra_url_rules(pid))

        return resp
