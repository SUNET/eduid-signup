import re

from eduid_signup.i18n import TranslationString as _


# http://www.regular-expressions.info/email.html
RFC2822_email = re.compile("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/="
                           "?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\."
                           ")+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")


class ValidationError(Exception):

    def __init__(self, msg, email=None):
        self.msg = msg
        self.email = email


def validate_email_format(email):
    return RFC2822_email.match(email.lower())


def validate_email(db, data):
    """Validate that a valid email address exist in the data dictionary"""
    try:
        email = data['email']
    except KeyError:
        raise ValidationError(_("Email is required"))

    if not validate_email_format(email):
        raise ValidationError(_("Email is not valid"), email)

    return email
