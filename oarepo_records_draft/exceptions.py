class InvalidRecordException(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors

    def __str__(self):
        return '{0}: {1}'.format(super().__str__(), str(self.errors))
