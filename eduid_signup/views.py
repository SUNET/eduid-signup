import os
import time
import datetime
from recaptcha.client import captcha
from bson import ObjectId

from pyramid.i18n import get_locale_name
from pyramid.httpexceptions import (HTTPFound, HTTPNotFound,
                                    HTTPMethodNotAllowed, HTTPBadRequest,)
from pyramid.security import forget
from pyramid.renderers import render_to_response
from pyramid.view import view_config
from pyramid.settings import asbool
from pyramid.response import FileResponse

from wsgi_ratelimit import is_ratelimit_reached

from eduid_am.tasks import update_attributes

from eduid_signup.emails import send_verification_mail, send_credentials
from eduid_signup.validators import validate_email, ValidationError
from eduid_signup.sna_callbacks import create_or_update_sna
from eduid_signup.utils import (verify_email_code, check_email_status,
                                generate_auth_token, AlreadyVerifiedException,
                                CodeDoesNotExists)
from eduid_signup.vccs import generate_password

import logging
logger = logging.getLogger(__name__)


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


@view_config(name='favicon.ico')
def favicon_view(context, request):
    path = os.path.dirname(__file__)
    icon = os.path.join(path, 'static', 'favicon.ico')
    return FileResponse(icon, request=request)


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

        request.session['email'] = email
        if is_ratelimit_reached(request.environ):
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
            return get_url_from_email_status(request, email)
        else:
            return {
                "error": True,
                "recaptcha_public_key": recaptcha_public_key
            }

    return HTTPMethodNotAllowed()


@view_config(route_name='success', renderer="templates/success.jinja2")
def success(context, request):

    if 'email' not in request.session:
        home_url = request.route_url("home")
        return HTTPFound(location=home_url)

    email = request.session['email']
    #secret = request.registry.settings.get('auth_shared_secret')
    #timestamp = "{:x}".format(int(time.time()))
    #nonce = os.urandom(16).encode('hex')
    #auth_token = generate_auth_token(secret, email, nonce, timestamp)

    return {
        #"profile_link": request.registry.settings.get("profile_link", "#"),
        "email": email,
        #"nonce": nonce,
        #"timestamp": timestamp,
        #"auth_token": auth_token,
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


@view_config(route_name='review_fetched_info',
             renderer='templates/review_fetched_info.jinja2')
def review_fetched_info(context, request):

    if not 'social_info' in request.session:
        raise HTTPBadRequest()

    social_info = request.session.get('social_info', {})
    email = social_info.get('email', None)

    mail_registered = False
    if email:
        signup_user = request.db.registered.find_one({
            "email": email,
            "verified": True
        })

        try:
            am_user_exists = request.userdb.exists_by_filter({
                'mailAliases': {
                    '$elemMatch': {
                        'email': email,
                        'verified': True
                    }
                }
            })
        except request.userdb.exceptions.UserDoesNotExist:
            am_user_exists = None

        mail_registered = signup_user or am_user_exists

    if request.method == 'GET':
        return {
            'social_info': social_info,
            'mail_registered': mail_registered,
            'mail_empty': not email,
            'reset_password_link': request.registry.settings['reset_password_link'],
        }

    else:
        if request.POST.get('action', 'cancel') == 'accept':
            create_or_update_sna(request)
            raise HTTPFound(location=request.route_url('sna_account_created'))
        else:
            if request.session is not None:
                request.session.delete()
            headers = forget(request)
            raise HTTPFound(location=request.route_url('home'),
                            headers=headers)


def registered_completed(request, user, context=None):
    if context is None:
        context = {}
    password_id = ObjectId()
    (password, salt) = generate_password(request.registry.settings,
                                         password_id, user,
                                         )
    request.db.registered.update(
        {
            'email': user.get('email'),
        }, {
            '$push': {
                'passwords': {
                    'id': password_id,
                    'salt': salt,
                    'source': 'signup',
                    'created_ts': datetime.datetime.utcnow(),
                }
            },
        }, safe=True)

    user_id = user.get("_id")

    # Send the signal to the attribute manager so it can update
    # this user's attributes in the IdP
    update_attributes.delay('eduid_signup', str(user_id))

    email = user.get('email')
    secret = request.registry.settings.get('auth_shared_secret')
    timestamp = '{:x}'.format(int(time.time()))
    nonce = os.urandom(16).encode('hex')

    auth_token = generate_auth_token(secret, email, nonce, timestamp)

    context.update({
        "profile_link": request.registry.settings.get("profile_link", "#"),
        "password": password,
        "email": email,
        "nonce": nonce,
        "timestamp": timestamp,
        "auth_token": auth_token,
    })

    if request.registry.settings.get("default_finish_url"):
        context['finish_url'] = request.registry.settings.get("default_finish_url")

    logger.debug("Context Finish URL : {!r}".format(context.get('finish_url')))

    if request.registry.settings.get("email_credentials", False):
        send_credentials(request, email, password)

    return context


@view_config(route_name='email_verification_link',
             renderer="templates/account_created.jinja2")
def email_verification_link(context, request):

    try:
        verify_email_code(request.db.registered, context.code)
    except AlreadyVerifiedException:
        return {
            'email_already_verified': True,
            "reset_password_link": request.registry.settings.get("reset_password_link", "#"),
        }
    except CodeDoesNotExists:
        return {
            "code_does_not_exists": True,
            "code_form": request.route_path('verification_code_form'),
            "signup_link": request.route_path('home'),
        }

    user = request.db.registered.find_one({
        'code': context.code
    })

    return registered_completed(request, user, {'from_email': True})


@view_config(route_name='verification_code_form',
             renderer="templates/verification_code_form.jinja2")
def verification_code_form(context, request):
    context = {}
    if request.method == 'POST':
        try:
            try:
                code = request.POST['code']
                verify_email_code(request.db.registered, code)
                user = request.db.registered.find_one({
                    'code': code
                })
                # XXX at this stage the confirmation code is marked as 'used' but no
                # credential have been created yet. If that fails (done beyond registered_completed),
                # the user will get an error and when retrying will get a message saying the email
                # address has already been verified. The user *is* given the possibility to reset
                # the password at that point, but it would be less surprising if the code was only
                # marked as 'used' when everything worked as expected.
                return registered_completed(request, user, {'from_email': True})
            except AlreadyVerifiedException:
                context = {
                    'email_already_verified': True,
                    'reset_password_link': request.registry.settings.get('reset_password_link', '#'),
                }
        except CodeDoesNotExists:
            context = {
                'code_does_not_exists': True,
                'code_form': request.route_path('verification_code_form'),
                'signup_link': request.route_path('home'),
            }
    return context


@view_config(route_name='sna_account_created',
             renderer="templates/account_created.jinja2")
def account_created_from_sna(context, request):

    user = request.db.registered.find_one({
        'email': request.session.get('email')
    })

    return registered_completed(request, user)


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
    template = 'templates/help-%s.jinja2' % locale_name

    return render_to_response(template, {}, request=request)


@view_config(route_name='error500test')
def error500view(context, request):
    raise Exception()


@view_config(route_name='error500', renderer='templates/error500.jinja2')
def exception_view(context, request):
    logger.error("The error was: %s" % context, exc_info=(context))
    request.response.status = 500
    #message = getattr(context, 'message', '')
    # `message' might include things like database connection details (with authentication
    # parameters), so it should NOT be displayed to the user.
    return {'msg': 'Code exception'}


@view_config(route_name='error404', renderer='templates/error404.jinja2')
def not_found_view(context, request):
    request.response.status = 404
    return {}


@view_config(route_name='set_language', request_method='GET')
def set_language(context, request):
    settings = request.registry.settings
    lang = request.GET.get('lang', 'en')
    if lang not in settings['available_languages']:
        return HTTPNotFound()

    url = request.environ.get('HTTP_REFERER', None)
    if url is None:
        url = request.route_path('home')
    response = HTTPFound(location=url)

    cookie_domain = settings.get('lang_cookie_domain', None)
    cookie_name = settings.get('lang_cookie_name')

    extra_options = {}
    if cookie_domain is not None:
        extra_options['domain'] = cookie_domain

    extra_options['httponly'] = asbool(settings.get('session.httponly'))
    extra_options['secure'] = asbool(settings.get('session.secure'))

    response.set_cookie(cookie_name, value=lang, **extra_options)

    return response
