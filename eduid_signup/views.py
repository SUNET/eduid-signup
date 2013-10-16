import os
import time
from recaptcha.client import captcha
from bson import ObjectId

from pyramid.i18n import get_locale_name
from pyramid.httpexceptions import HTTPFound, HTTPMethodNotAllowed
from pyramid.renderers import render_to_response
from pyramid.view import view_config

from wsgi_ratelimit import is_ratelimit_reached

from eduid_am.tasks import update_attributes

from eduid_signup.emails import send_verification_mail
from eduid_signup.validators import validate_email, ValidationError
from eduid_signup.utils import (verificate_code, check_email_status,
                                generate_auth_token)
from eduid_signup.vccs import generate_password


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
def success(request):

    if 'email' not in request.session:
        home_url = request.route_url("home")
        return HTTPFound(location=home_url)

    email = request.session['email']
    secret = request.registry.settings.get('auth_shared_secret')
    timestamp = "{:x}".format(int(time.time()))
    nonce = os.urandom(16).encode('hex')
    auth_token = generate_auth_token(secret, email, nonce, timestamp)

    return {
        "profile_link": request.registry.settings.get("profile_link", "#"),
        "email": email,
        "nonce": nonce,
        "timestamp": timestamp,
        "auth_token": auth_token,
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


def registered_completed(request, user, context=None):
    if context is None:
        context = {}
    password_id = str(ObjectId())
    (password, salt) = generate_password(
        request.registry.settings.get('vccs_url'),
        str(password_id),
        user.get('email'),
    )

    request.db.registered.update(
        {
            'email': user.get('email'),
        }, {
            '$push': {
                'passwords': {
                    'id': password_id,
                    'salt': salt,
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

    return context


@view_config(route_name='email_verification_link',
             renderer="templates/account_created.jinja2")
def email_verification_link(context, request):

    verificate_code(request.db.registered, context.code)

    user = request.db.registered.find_one({
        'code': context.code
    })

    return registered_completed(request, user, {'from_email': True})


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
    template = 'eduid_signup:templates/help-%s.jinja2' % locale_name

    return render_to_response(template, {}, request=request)
