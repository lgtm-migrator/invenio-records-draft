from flask import Blueprint

from .edit import EditRecordAction
from .publish import PublishRecordAction
from .unpublish import UnpublishRecordAction

blueprint = Blueprint("invenio_records_draft", __name__, url_prefix="/")

__all__ = ('blueprint', 'EditRecordAction', 'PublishRecordAction', 'UnpublishRecordAction')
