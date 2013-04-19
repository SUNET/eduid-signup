from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from eduid_signup.emails import send_verification_mail
from eduid_signup.i18n import TranslationString as _
from eduid_signup.validators import email_format_validator, required_validator
from eduid_signup.utils import verificate_code


@view_config(route_name='home', renderer='templates/home.jinja2')
def home(request):
    response = {}
    if request.method == 'POST':
        email = request.POST.get("email", None)

        response = required_validator(
            request.POST,
            "email",
            _("Email is required")
        )

        if not response:
            response = email_format_validator(email)

        if response:
            return response

        else:
            # verify if mail was registered before:
            registered = request.db.registered
            if registered.find({"email": email}).count() > 0:
                return {"email_error": _("This email is already registered"),
                        "email": email}

            send_verification_mail(request, email)

            success_url = request.route_url("success")
            return HTTPFound(location=success_url)

    return response


@view_config(route_name='success', renderer="templates/success.jinja2")
def success(request):
    return {
        "profile_link": request.registry.settings.get("profile_link", "#")
    }


@view_config(route_name='email_verification_link',
             renderer="templates/email_verified.jinja2")
def email_verification_link(context, request):
    verificate_code(request.db.registered, context.code)
    return {
        "profile_link": request.registry.settings.get("profile_link", "#")
    }
