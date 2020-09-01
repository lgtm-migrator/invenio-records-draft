from flask import Blueprint

from oarepo_records_draft.types import DraftPublishedRecordConfiguration
from .actions.edit import EditRecordAction
from .actions.publish import PublishRecordAction
from .actions.unpublish import UnpublishRecordAction


def register_blueprint_actions(blueprint, base_route, actions):
    for k, v in actions.items():
        blueprint.add_url_rule(
            rule=f'{base_route}/{k}',
            view_func=v)


def register_blueprint(app, current_drafts):
    if 'oarepo_records_draft' in app.blueprints:
        return

    blueprint = Blueprint("oarepo_records_draft", __name__, url_prefix="/")

    for endpoint in current_drafts.managed_records:  # type: DraftPublishedRecordConfiguration
        register_blueprint_actions(
            blueprint,
            endpoint.draft.rest['item_route'],
            endpoint.draft.extra['actions']
        )
        register_blueprint_actions(
            blueprint,
            endpoint.draft.rest['item_route'],
            {
                'publish': PublishRecordAction.as_view(
                    PublishRecordAction.view_name.format(endpoint.draft.rest_name),
                    endpoint=endpoint.draft
                )
            }
        )

        register_blueprint_actions(
            blueprint,
            endpoint.published.rest['item_route'],
            endpoint.published.extra['actions']
        )
        register_blueprint_actions(
            blueprint,
            endpoint.published.rest['item_route'],
            {
                'unpublish': UnpublishRecordAction.as_view(
                    UnpublishRecordAction.view_name.format(endpoint.published.rest_name),
                    endpoint=endpoint.published
                ),
                'edit': EditRecordAction.as_view(
                    EditRecordAction.view_name.format(endpoint.published.rest_name),
                    endpoint=endpoint.published
                )
            }
        )

    app.register_blueprint(blueprint)
