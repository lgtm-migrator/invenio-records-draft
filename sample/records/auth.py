from flask_login import current_user


def allow_authenticated(*args, **kwargs):
    """Return permission that always allow an access.

    :returns: A object instance with a ``can()`` method.
    """
    return type('Allow', (), {'can': lambda self: current_user.is_authenticated})()
