class InvalidRecordException(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.message = message
        self.errors = errors

    def __str__(self):
        return '{0}: {1}'.format(super().__str__(), str(self.errors))


class FatalDraftException(Exception):
    """
    If you raise this exception for example in marshmallow validation, the process will be
    aborted and no record will be created/updated.

    Use this with caution as it prevents people inserting records. A common use case might
    be when marshmallow schema needs to create a sub-record and it can not be created
    for security reasons.
    """
    pass
