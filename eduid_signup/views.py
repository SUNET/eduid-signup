from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from eduid_signup.emails import send_verification_mail
from eduid_signup.validators import validate_email, ValidationError
from eduid_signup.utils import verificate_code


@view_config(route_name='home', renderer='templates/home.jinja2')
def home(request):
    if request.method == 'POST':
        try:
            email = validate_email(request.db, request.POST)
        except ValidationError as error:
            return {'email_error': error.msg, 'email': error.email}

        send_verification_mail(request, email)

        success_url = request.route_url("success")
        return HTTPFound(location=success_url)

    return {}


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
