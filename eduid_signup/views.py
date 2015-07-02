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

from eduid_am.tasks import update_attributes_keep_result

from eduid_signup.i18n import TranslationString as _
from eduid_signup.emails import send_verification_mail, send_credentials
from eduid_signup.validators import validate_email, ValidationError
from eduid_signup.sna_callbacks import create_or_update_sna
from eduid_signup.utils import (verify_email_code, check_email_status,
                                generate_auth_token, AlreadyVerifiedException,
                                CodeDoesNotExists, record_tou)
from eduid_signup.vccs import generate_password

import logging
logger = logging.getLogger(__name__)


EMAIL_STATUS_VIEWS = {
    'new': None,
    'not_verified': 'resend_email_verification',
    'verified': 'email_already_registered'
}


def get_url_from_email_status(request, email):
    """
    Return a view depending on
    the verification status of the provided email.

    :param request: the request
    :type request: WebOb Request
    :param email: the email
    :type email: string

    :return: redirect response
    """
    status = check_email_status(request.userdb, email)
    logger.debug("e-mail {!s} status: {!s}".format(email, status))
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
    """
    Home view.
    If request.method is GET, 
    return the initial signup form.
    If request.method is POST, 
    validate the sent email and
    redirects as appropriate.
    """
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
        remote_ip = request.environ.get('REMOTE_ADDR', '')
        logger.debug('Presenting CAPTCHA to {!s} (email {!s}) in home()'.format(remote_ip, email))
        trycaptcha_url = request.route_url("trycaptcha")
        return HTTPFound(location=trycaptcha_url)

    return context


@view_config(route_name='trycaptcha', renderer='templates/trycaptcha.jinja2')
def trycaptcha(request):
    """
    Kantara requires a check for humanness even at level AL1.
    """

    if 'email' not in request.session:
        home_url = request.route_url("home")
        return HTTPFound(location=home_url)

    settings = request.registry.settings

    remote_ip = request.environ.get("REMOTE_ADDR", '')
    recaptcha_public_key = settings.get("recaptcha_public_key", '')
    if request.method == 'GET':
        logger.debug("Presenting CAPTCHA to {!s} (email {!s})".format(remote_ip, request.session['email']))
        return {
            'recaptcha_public_key': recaptcha_public_key
        }

    if request.method == 'POST':
        challenge_field = request.POST.get('recaptcha_challenge_field', '')
        response_field = request.POST.get('recaptcha_response_field', '')

        response = captcha.submit(
            challenge_field,
            response_field,
            settings.get("recaptcha_private_key", ''),
            remote_ip,
        )

        if response.is_valid or not recaptcha_public_key:
            logger.debug("Valid CAPTCHA response (or CAPTCHA disabled) from {!r}".format(remote_ip))

            # recaptcha_public_key not set in development environment, just accept
            email = request.session['email']
            return get_url_from_email_status(request, email)

        logger.debug("Invalid CAPTCHA response from {!r}: {!r}".format(remote_ip, response.error_code))
        return {
            "error": True,
            "recaptcha_public_key": recaptcha_public_key
        }

    return HTTPMethodNotAllowed()


@view_config(route_name='success', renderer="templates/success.jinja2")
def success(request):
    """
    After a successful operation with no
    immediate follow up on the web.
    """

    if 'email' not in request.session:
        home_url = request.route_url("home")
        return HTTPFound(location=home_url)

    email = request.session['email']
    #secret = request.registry.settings.get('auth_shared_secret')
    #timestamp = "{:x}".format(int(time.time()))
    #nonce = os.urandom(16).encode('hex')
    #auth_token = generate_auth_token(secret, email, nonce, timestamp)

    logger.debug("Successful signup for {!s}".format(email))
    return {
        #"profile_link": request.registry.settings.get("profile_link", "#"),
        "email": email,
        #"nonce": nonce,
        #"timestamp": timestamp,
        #"auth_token": auth_token,
    }


@view_config(route_name='resend_email_verification',
             renderer='templates/resend_email_verification.jinja2')
def resend_email_verification(request):
    """
    The user has no yet verified the email address.
    Send a verification message to the address so it can be verified.
    """
    if request.method == 'POST':
        email = request.session.get('email', '')
        logger.debug("Resend email confirmation to {!s}".format(email))
        if email:
            send_verification_mail(request, email)
            url = request.route_url('success')

            return HTTPFound(location=url)

    return {}


@view_config(route_name='email_already_registered',
             renderer='templates/already_registered.jinja2')
def already_registered(request):
    """
    There is already an account with that address.
    Return a link to reset the password for that account.
    """
    logger.debug("E-mail already registered: {!s}".format(request.session.get('email')))
    return {
        'reset_password_link': request.registry.settings.get(
            'reset_password_link', '#'),
    }


@view_config(route_name='review_fetched_info',
             renderer='templates/review_fetched_info.jinja2')
def review_fetched_info(request):
    """
    Once user info has been retrieved from a social network,
    present it to the user so she can review and accept it.
    """

    debug_mode = request.registry.settings.get('development', False)
    if not 'social_info' in request.session and not debug_mode:
        raise HTTPBadRequest()

    social_info = request.session.get('social_info', {})
    email = social_info.get('email', None)

    if debug_mode:
        social_info = {
            'email': 'dummy@eduid.se',
            'screen_name': 'dummy',
            'first_name': 'dummy',
            'last_name': 'dummy',
        }

    mail_registered = False
    if email:
        signup_user = request.db.registered.find_one({
            "email": email,
            "verified": True
        })

        try:
            am_user = request.userdb.get_user_by_email(email)
        except request.userdb.exceptions.UserDoesNotExist:
            pass
        else:
            raise HTTPFound(location=request.route_url('email_already_registered'))

        mail_registered = signup_user

    if request.method == 'GET':
        return {
            'social_info': social_info,
            'mail_registered': bool(mail_registered),
            'mail_empty': not email,
            'reset_password_link': request.registry.settings['reset_password_link'],
        }

    elif email:
        if request.POST.get('action', 'cancel') == 'accept':
            create_or_update_sna(request, social_info, signup_user)
            raise HTTPFound(location=request.route_url('sna_account_created'))
        else:
            if request.session is not None:
                request.session.delete()
            headers = forget(request)
            raise HTTPFound(location=request.route_url('home'),
                            headers=headers)
    else:
        raise HTTPBadRequest()


def registered_completed(request, user, context=None):
    """
    After a successful registration
    (through the mail or through a social network),
    generate a password,
    add it to the registration record in the registrations db,
    update the attribute manager db with the new account,
    and send the pertinent information to the user.
    """
    user_id = user.get("_id")
    eppn = user.get('eduPersonPrincipalName')

    logger.info("Completing registration for user {!s}/{!s} (first created: {!s})".format(
        user_id, eppn, user.get('created_ts')))

    if context is None:
        context = {}
    password_id = ObjectId()
    (password, salt) = generate_password(request.registry.settings,
                                         str(password_id), user,
                                         )
    request.db.registered.update(
        {
            'eduPersonPrincipalName': eppn,
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

    logger.debug("Asking for sync by Attribute Manager")
    # Send the signal to the attribute manager so it can update
    # this user's attributes in the IdP
    rtask = update_attributes_keep_result.delay('eduid_signup', str(user_id))

    eppn = user.get('eduPersonPrincipalName')
    secret = request.registry.settings.get('auth_shared_secret')
    timestamp = '{:x}'.format(int(time.time()))
    nonce = os.urandom(16).encode('hex')

    timeout = request.registry.settings.get("account_creation_timeout", 10)
    try:
        result = rtask.get(timeout=timeout)
        logger.debug("Attribute Manager sync result: {!r}".format(result))
    except Exception:
        logger.exception("Failed Attribute Manager sync request")
        message = _('There were problems with your submission. '
                    'You may want to try again later, '
                    'or contact the site administrators.')
        request.session.flash(message)
        url = request.route_path('home')
        raise HTTPFound(location=url)

    auth_token = generate_auth_token(secret, eppn, nonce, timestamp)

    context.update({
        "profile_link": request.registry.settings.get("profile_link", "#"),
        "password": password,
        "email": user.get('email'),
        "eppn": eppn,
        "nonce": nonce,
        "timestamp": timestamp,
        "auth_token": auth_token,
    })

    if request.registry.settings.get("default_finish_url"):
        context['finish_url'] = request.registry.settings.get("default_finish_url")

    logger.debug("Context Finish URL : {!r}".format(context.get('finish_url')))

    if request.registry.settings.get("email_credentials", False):
        send_credentials(request, eppn, password)

    # Record the acceptance of the terms of use

    record_tou(request, user_id, 'signup')

    logger.info("Signup process for new user {!s}/{!s} complete".format(user_id, eppn))
    return context


@view_config(route_name='email_verification_link',
             renderer="templates/account_created.jinja2")
def email_verification_link(request):
    """
    View for the link sent to the user's mail
    so that she can verify the address she has provided.
    """

    logger.debug("Trying to confirm e-mail using confirmation link")
    code = request.matchdict['code']
    try:
        verify_email_code(request.db.registered, code)
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
        'code': code,
    })

    return registered_completed(request, user, {'from_email': True})


@view_config(route_name='verification_code_form',
             renderer="templates/verification_code_form.jinja2")
def verification_code_form(request):
    """
    form to enter the verification code
    """
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
def account_created_from_sna(request):
    """
    View where the registration from a social network is completed,
    after the user has reviewed the information fetched from the s.n.
    """

    user = request.db.registered.find_one({
        'email': request.session.get('email')
    })

    return registered_completed(request, user)


@view_config(route_name='help')
def help(request):
    """
    help view
    """
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
def error500view(request):
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
def not_found_view(request):
    request.response.status = 404
    return {}


@view_config(route_name='set_language', request_method='GET')
def set_language(request):
    import re

    settings = request.registry.settings
    lang = request.GET.get('lang', 'en')
    if lang not in settings['available_languages']:
        return HTTPNotFound()

    url = request.environ.get('HTTP_REFERER', None)
    host = request.environ.get('HTTP_HOST', None)

    signup_hostname = settings.get('signup_hostname')
    signup_baseurl = settings.get('signup_baseurl')

    # To avoid malicious redirects, using header injection, we only
    # allow the client to be redirected to an URL that is within the
    # predefined scope of the application.
    allowed_url = re.compile('^(http|https)://' + signup_hostname + '[:]{0,1}\d{0,5}($|/)')
    allowed_host = re.compile('^' + signup_hostname + '[:]{0,1}\d{0,5}$')

    if url is None or not allowed_url.match(url):
        url = signup_baseurl
    elif host is None or not allowed_host.match(host):
        url = signup_baseurl

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
