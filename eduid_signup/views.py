from recaptcha.client import captcha

from pyramid.i18n import get_locale_name
from pyramid.httpexceptions import HTTPFound, HTTPMethodNotAllowed
from pyramid.renderers import render_to_response
from pyramid.view import view_config

from wsgi_ratelimit import is_ratelimit_reached

from eduid_signup.emails import send_verification_mail
from eduid_signup.validators import validate_email, ValidationError
from eduid_signup.utils import verificate_code, check_email_status


EMAIL_STATUS_VIEWS = {
    'new': None,
    'not_verified': 'resend_email_verification',
    'verified': 'email_already_registered'
}


def get_url_from_email_status(request, email):
    status = check_email_status(request.db, email)
    if status == 'new':
        send_verification_mail(request, email)
        namedview = 'success'
    else:
        request.session['email'] = email
        namedview = EMAIL_STATUS_VIEWS[status]
    url = request.route_url(namedview)
    return HTTPFound(location=url)


@view_config(route_name='home', renderer='templates/home.jinja2')
def home(request):
    context = {}
    if request.method == 'POST':
        try:
            email = validate_email(request.db, request.POST)
        except ValidationError as error:
            context.update({
                'email_error': error.msg,
                'email': error.email
            })
            return context

        if is_ratelimit_reached(request.environ):
            request.session['email'] = email
            trycaptcha_url = request.route_url("trycaptcha")
            return HTTPFound(location=trycaptcha_url)

        return get_url_from_email_status(request, email)

    return context


@view_config(route_name='trycaptcha', renderer='templates/trycaptcha.jinja2')
def trycaptcha(request):

    if 'email' not in request.session:
        home_url = request.route_url("home")
        return HTTPFound(location=home_url)

    settings = request.registry.settings

    recaptcha_public_key = settings.get("recaptcha_public_key", ''),
    if request.method == 'GET':
        return {
            'recaptcha_public_key': recaptcha_public_key
        }

    elif request.method == 'POST':
        challenge_field = request.POST.get('recaptcha_challenge_field', '')
        response_field = request.POST.get('recaptcha_response_field', '')

        response = captcha.submit(
            challenge_field,
            response_field,
            settings.get("recaptcha_private_key", ''),
            request.environ.get("REMOTE_ADDRESS", ''),
        )

        if response.is_valid:
            email = request.session['email']
            del request.session['email']
            return get_url_from_email_status(request, email)
        else:
            return {
                "error": True,
                "recaptcha_public_key": recaptcha_public_key
            }

    return HTTPMethodNotAllowed()


@view_config(route_name='success', renderer="templates/success.jinja2")
def success(request):
    return {
        "profile_link": request.registry.settings.get("profile_link", "#"),
    }


@view_config(route_name='resend_email_verification',
             renderer='templates/resend_email_verification.jinja2')
def resend_email_verification(context, request):
    if request.method == 'POST':
        email = request.session.get('email', '')
        if email:
            send_verification_mail(request, email)
            url = request.route_url('success')
            return HTTPFound(location=url)

    return {}


@view_config(route_name='email_already_registered',
             renderer='templates/already_registered.jinja2')
def already_registered(context, request):
    return {
        'reset_password_link': request.registry.settings.get(
            'reset_password_link', '#'),
    }


@view_config(route_name='email_verification_link',
             renderer="templates/email_verified.jinja2")
def email_verification_link(context, request):
    verificate_code(request.db.registered, context.code)
    return {
        "profile_link": request.registry.settings.get("profile_link", "#")
    }


@view_config(route_name='help')
def help(request):
    # We don't want to mess up the gettext .po file
    # with a lot of strings which don't belong to the
    # application interface.
    #
    # We consider the HELP as application content
    # so we simple use a different template for each
    # language. When a new locale is added to the
    # application it needs to translate the .po files
    # as well as this template

    locale_name = get_locale_name(request)
    template = 'eduid_signup:templates/help-%s.jinja2' % locale_name

    return render_to_response(template, {}, request=request)
