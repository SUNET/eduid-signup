import re

from eduid_signup.i18n import TranslationString as _


# http://www.regular-expressions.info/email.html
RFC2822_email = re.compile("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/="
                           "?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\."
                           ")+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")


def email_format_validator(email):
    if not RFC2822_email.match(email):
        return {"email_error": _("Email is not valid"),
                "email": email}


def required_validator(post, fieldname, message):
    if not fieldname.get(fieldname, None):
        return {"{0}_error".format(fieldname): message}
