import re

from pyramid.view import view_config
from pyramid.i18n import TranslationString as _
from pyramid.i18n import get_localizer


# http://www.regular-expressions.info/email.html
RFC2822_email = re.compile("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/="
                           "?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\."
                           ")+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")


@view_config(route_name='home', renderer='templates/home.jinja2')
def home(request):
    localizer = get_localizer(request)
    if request.is_body_readable:
        email = request.POST.get("email", None)
        if email is None:
            return {}
        if not RFC2822_email.match(email):
            error_message = _("Email is not valid")
            return {"email_error": localizer.translate(error_message),
                    "email": email}
        else:
            # Do the registration staff
            # save email
            pass

    return {}
