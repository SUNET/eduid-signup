from datetime import datetime
import re

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from eduid_signup.i18n import TranslationString as _


# http://www.regular-expressions.info/email.html
RFC2822_email = re.compile("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/="
                           "?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\."
                           ")+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")


@view_config(route_name='home', renderer='templates/home.jinja2')
def home(request):
    if request.method == 'POST':
        email = request.POST.get("email", None)
        if email is None:
            return {"email_error": _("Email is required")}
        if not RFC2822_email.match(email):
            return {"email_error": _("Email is not valid"),
                    "email": email}
        else:
            # Do the registration staff
            # if mail was registered before:
            registered = request.db.registered
            if registered.find({"email": email}).count() > 0:
                return {"email_error": _("This email is already registered"),
                        "email": email}

            now = datetime.utcnow()
            request.db.registered.insert({
                "email": email,
                "date": now
            })
            success_url = request.route_url("success")
            return HTTPFound(location=success_url)

    return {}


@view_config(route_name='success', renderer="templates/success.jinja2")
def success(request):
    return {
        "profile_link": request.registry.settings.get("profile_link", "#")
    }
