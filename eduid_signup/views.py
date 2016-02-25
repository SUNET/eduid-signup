import os
import re
import time
from recaptcha.client import captcha
from bson import ObjectId

from urllib2 import URLError
from pyramid.i18n import get_locale_name
from pyramid.httpexceptions import (HTTPFound, HTTPNotFound,
                                    HTTPMethodNotAllowed, HTTPBadRequest,)
from pyramid.security import forget
from pyramid.renderers import render_to_response
from pyramid.view import view_config

from eduid_am.tasks import update_attributes_keep_result

from eduid_signup.config import pyramid_unpack_config
from eduid_signup.i18n import TranslationString as _
from eduid_signup.emails import send_verification_mail, send_credentials
from eduid_signup.validators import validate_email, ValidationError
from eduid_signup.sna_callbacks import create_or_update_sna
from eduid_signup.utils import (verify_email_code, check_email_status,
                                generate_auth_token, AlreadyVerifiedException,
                                CodeDoesNotExists, record_tou)
from eduid_signup.vccs import generate_password
from eduid_userdb.signup import SignupUser
from eduid_userdb.password import Password

import logging
logger = logging.getLogger(__name__)


def get_url_from_email_status(request, email):
    """
    Return a view depending on the verification status of the provided email.

    If a user with this (verified) e-mail address exist in the central eduid userdb,
    return view 'email_already_registered'.

    Otherwise, send a verification e-mail.

    :param request: the request
    :param email: the email

    :type request: pyramid.request.Request
    :type email: str | unicode

    :return: redirect response
    """
    status = check_email_status(request.userdb, request.signup_db, email)
    logger.debug("e-mail {!s} status: {!s}".format(email, status))
    if status == 'new':
        send_verification_mail(request, email)
        namedview = 'success'
    elif status == 'not_verified':
        request.session['email'] = email
        namedview = 'resend_email_verification'
    elif status == 'verified':
        request.session['email'] = email
        namedview = 'email_already_registered'
    else:
        raise NotImplementedError('Unknown e-mail status: {!r}'.format(status))
    url = request.route_url(namedview)

    return HTTPFound(location=url)


@view_config(name='favicon.ico')
def favicon_view(context, request):
    return HTTPFound(request.static_url('static/favicon.ico'))


@view_config(route_name='home', renderer='templates/home.jinja2')
def home(request):
    """
    Home view.
    If request.method is GET, return the initial signup form.
    If request.method is POST, validate the sent email and
    redirects as appropriate.

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    if request.method == 'POST':
        try:
            email = validate_email(request.POST)
        except ValidationError as error:
            return {
                'email_error': error.msg,
                'email': error.email
            }

        request.session['email'] = email
        remote_ip = request.environ.get('REMOTE_ADDR', '')
        logger.debug('Presenting CAPTCHA to {!s} (email {!s}) in home()'.format(remote_ip, email))
        trycaptcha_url = request.route_url("trycaptcha")
        return HTTPFound(location=trycaptcha_url)

    return {}


@view_config(route_name='trycaptcha', renderer='templates/trycaptcha.jinja2')
def trycaptcha(request):
    """
    Kantara requires a check for humanness even at level AL1.

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    config = pyramid_unpack_config(request)
    context = {
        'recaptcha_public_key': config.recaptcha_public_key,
    }

    if 'email' not in request.session:
        home_url = request.route_url("home")
        logger.debug('No email in session, redirecting user to {!s}'.format(home_url))
        return HTTPFound(location=home_url)

    remote_ip = request.environ.get("REMOTE_ADDR", '')
    if request.method == 'GET':
        logger.debug("Presenting CAPTCHA to {!s} (email {!s})".format(remote_ip, request.session['email']))
        return context

    if request.method == 'POST':
        challenge_field = request.POST.get('recaptcha_challenge_field', '')
        response_field = request.POST.get('recaptcha_response_field', '')

        for i in range(0, 3):
            try:
                response = captcha.submit(
                    challenge_field,
                    response_field,
                    config.recaptcha_private_key,
                    remote_ip,
                    #use_ssl=True
                )
                logger.debug("Sent the CAPTCHA with the user's response to google")
                break
            except URLError:
                if i < 2:
                    logger.debug("Caught URLError while sending recaptcha, trying again.")
                    time.sleep(0.5)
                else:
                    logger.debug("Caught URLError while sending recaptcha, giving up.")
                    raise

        if response.is_valid or not config.recaptcha_public_key:
            logger.debug("Valid CAPTCHA response (or CAPTCHA disabled) from {!r}".format(remote_ip))

            # recaptcha_public_key not set in development environment, just accept
            email = request.session['email']
            return get_url_from_email_status(request, email)

        logger.debug("Invalid CAPTCHA response from {!r}: {!r}".format(remote_ip, response.error_code))
        context['error'] = True
        return context

    return HTTPMethodNotAllowed()


@view_config(route_name='success', renderer="templates/success.jinja2")
def success(request):
    """
    After a successful operation with no
    immediate follow up on the web.

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    config = pyramid_unpack_config(request)
    if 'email' not in request.session:
        home_url = request.route_url("home")
        return HTTPFound(location=home_url)

    email = request.session['email']

    logger.debug("Successful signup for {!s}".format(email))
    return {'email': email,
            }


@view_config(route_name='resend_email_verification',
             renderer='templates/resend_email_verification.jinja2')
def resend_email_verification(request):
    """
    The user has no yet verified the email address.
    Send a verification message to the address so it can be verified.

    :param request: Pyramid request
    :type request: pyramid.request.Request
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

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    config = pyramid_unpack_config(request)
    logger.debug("E-mail already registered: {!s}".format(request.session.get('email')))
    return {
        'reset_password_link': config.reset_password_link,
    }


@view_config(route_name='review_fetched_info',
             renderer='templates/review_fetched_info.jinja2')
def review_fetched_info(request):
    """
    Once user info has been retrieved from a social network,
    present it to the user so she can review and accept it.

    First, a GET renders the information for the user to review, then
    a POST is used to accept the information shown, or abort the signup.

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    config = pyramid_unpack_config(request)
    logger.debug("View review_fetched_info ({!s})".format(request.method))
    if 'social_info' not in request.session and not config.development:
        raise HTTPBadRequest()

    social_info = request.session.get('social_info', {})
    email = social_info.get('email', None)

    if config.development:
        social_info = {
            'email': 'dummy@eduid.se',
            'screen_name': 'dummy',
            'first_name': 'dummy',
            'last_name': 'dummy',
        }

    am_user = False
    if email:
        try:
            am_user = request.userdb.get_user_by_mail(email, raise_on_missing=True)
            logger.info("User {!s} found using email {!s}".format(am_user, email))
            raise HTTPFound(location=request.route_url('email_already_registered'))
        except request.userdb.exceptions.UserDoesNotExist:
            pass

    if request.method == 'GET':
        # If `mail_registered' is true, the user is told the address already exists and they
        # are given the option to do a password reset.
        #
        # If `mail_empty' is true, the user is told the Social network did not provide an e-mail
        # address and they need to press 'cancel' and choose another Signup method.
        res = {
            'social_info': social_info,
            'mail_registered': bool(am_user),
            'mail_empty': not email,
            'reset_password_link': config.reset_password_link,
        }
        logger.debug("Rendering review form: {!r}".format(res))
        return res

    if request.method == 'POST' and email and not am_user:
        if request.POST.get('action') == 'accept':
            logger.debug("Proceeding with social signup of {!r}: {!r}".format(email, social_info))
            create_or_update_sna(request, social_info)
            raise HTTPFound(location=request.route_url('sna_account_created'))
        else:
            logger.debug("Social signup aborted")
            if request.session is not None:
                request.session.delete()
            headers = forget(request)
            raise HTTPFound(location=request.route_url('home'),
                            headers=headers)
    else:
        raise HTTPBadRequest()


def registered_completed(request, signup_user, context=None):
    """
    After a successful registration
    (through the mail or through a social network),
    generate a password,
    add it to the registration record in the registrations db,
    update the attribute manager db with the new account,
    and send the pertinent information to the user.

    :param request: Pyramid request
    :param signup_user: SignupUser instance

    :type request: pyramid.request.Request
    :type signup_user: SignupUser
    """
    config = pyramid_unpack_config(request)
    logger.info("Completing registration for user {!s}/{!s}".format(signup_user.user_id, signup_user.eppn))

    if context is None:
        context = {}
    password_id = ObjectId()
    (password, salt) = generate_password(config, str(password_id), signup_user)
    credential = Password(credential_id=password_id, salt=salt, application='signup')
    signup_user.passwords.add(credential)
    # Record the acceptance of the terms of use
    record_tou(request, signup_user, 'signup')
    request.signup_db.save(signup_user)

    # Send the signal to the attribute manager so it can update
    # this user's attributes in the IdP
    logger.debug("Asking for sync of {!r} by Attribute Manager".format(str(signup_user.user_id)))
    try:
        rtask = update_attributes_keep_result.delay('eduid_signup', str(signup_user.user_id))
        timeout = config.account_creation_timeout
        result = rtask.get(timeout=timeout)
        logger.debug("Attribute Manager sync result: {!r}".format(result))
    except:
        logger.exception("Failed Attribute Manager sync request. trying again")
        try:
            rtask = update_attributes_keep_result.delay('eduid_signup', str(signup_user.user_id))
            timeout = config.account_creation_timeout * 2
            result = rtask.get(timeout=timeout)
            logger.debug("Attribute Manager sync result: {!r}".format(result))
        except:
            logger.exception("Failed Attribute Manager sync request")
            message = _('Sorry, but the requested page is unavailable due to a server hiccup. '
                        'Our engineers have been notified, so check back later. ')
            request.session.flash(message)
            url = request.route_path('home')
            raise HTTPFound(location=url)

    secret = config.auth_shared_secret
    timestamp = '{:x}'.format(int(time.time()))
    nonce = os.urandom(16).encode('hex')
    auth_token = generate_auth_token(secret, signup_user.eppn, nonce, timestamp)

    context.update({
        "profile_link": config.profile_link,
        "password": password,
        "email": signup_user.mail_addresses.primary.email,
        "eppn": signup_user.eppn,
        "nonce": nonce,
        "timestamp": timestamp,
        "auth_token": auth_token,
    })

    if config.default_finish_url:
        # XXX shouldn't this only happen if there is no context['finish_url']?
        context['finish_url'] = config.default_finish_url

    logger.debug("Context Finish URL : {!r}".format(context.get('finish_url')))

    if config.email_credentials:
        send_credentials(request, signup_user.eppn, password)

    logger.info("Signup process for new user {!s}/{!s} complete".format(signup_user.user_id, signup_user.eppn))
    return context


@view_config(route_name='email_verification_link',
             renderer="templates/account_created.jinja2")
def email_verification_link(request):
    """
    View for the link sent to the user's mail
    so that she can verify the address she has provided.

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    logger.debug("Trying to confirm e-mail using confirmation link")
    code = request.matchdict['code']
    return _verify_code(request, code)


@view_config(route_name='verification_code_form',
             renderer="templates/verification_code_form.jinja2")
def verification_code_form(request):
    """
    form to enter the verification code

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    if request.method == 'POST':
        code = request.POST['code']
        return _verify_code(request, code)
    return {}


def _verify_code(request, code):
    """
    Common code for the link- and form-based code verification.

    :param request: Pyramid request
    :param code: Code given by the user

    :type request: pyramid.request.Request
    :return:
    """
    config = pyramid_unpack_config(request)

    try:
        signup_user = verify_email_code(request.signup_db, code)
        # XXX at this stage the confirmation code is marked as 'used' but no
        # credential have been created yet. If that fails (done beyond registered_completed),
        # the user will get an error and when retrying will get a message saying the email
        # address has already been verified. The user *is* given the possibility to reset
        # the password at that point, but it would be less surprising if the code was only
        # marked as 'used' when everything worked as expected.
    except AlreadyVerifiedException:
        # Should not be able to get here. Raise exception instead?
        logger.error("The pending MailAddress was verified already. Should not happen!")
        return {
            'email_already_verified': True,
            "reset_password_link": config.reset_password_link,
        }
    except CodeDoesNotExists:
        return {
            "code_does_not_exists": True,
            "code_form": request.route_path('verification_code_form'),
            "signup_link": request.route_path('home'),
        }

    return registered_completed(request, signup_user, {'from_email': True})


@view_config(route_name='sna_account_created',
             renderer="templates/account_created.jinja2")
def account_created_from_sna(request):
    """
    View where the registration from a social network is completed,
    after the user has reviewed the information fetched from the s.n.

    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    user = request.signup_db.get_user_by_mail(request.session.get('email'),
                                              raise_on_missing=True,
                                              include_unconfirmed=True,
                                              )

    assert isinstance(user, SignupUser)

    return registered_completed(request, user)


@view_config(route_name='help')
def help(request):
    """
    help view

    :param request: Pyramid request
    :type request: pyramid.request.Request
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
    """
    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    logger.error("The error was: %s" % context, exc_info=(context))
    request.response.status = 500
    # message = getattr(context, 'message', '')
    # `message' might include things like database connection details (with authentication
    # parameters), so it should NOT be displayed to the user.
    return {'msg': 'Code exception'}


@view_config(route_name='error404', renderer='templates/error404.jinja2')
def not_found_view(request):
    """
    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    request.response.status = 404
    return {}


@view_config(route_name='set_language', request_method='GET')
def set_language(request):
    """
    :param request: Pyramid request
    :type request: pyramid.request.Request
    """
    config = pyramid_unpack_config(request)
    lang = request.GET.get('lang', 'en')
    if lang not in config.available_languages:
        return HTTPNotFound()

    url = request.environ.get('HTTP_REFERER', None)
    host = request.environ.get('HTTP_HOST', None)

    # To avoid malicious redirects, using header injection, we only
    # allow the client to be redirected to an URL that is within the
    # predefined scope of the application.
    allowed_url = re.compile('^(http|https)://' + config.signup_hostname + '[:]{0,1}\d{0,5}($|/)')
    allowed_host = re.compile('^' + config.signup_hostname + '[:]{0,1}\d{0,5}$')

    if url is None or not allowed_url.match(url):
        url = config.signup_baseurl
    elif host is None or not allowed_host.match(host):
        url = config.signup_baseurl

    response = HTTPFound(location=url)

    extra_options = {}
    if config.lang_cookie_domain is not None:
        extra_options['domain'] = config.lang_cookie_domain

    extra_options['httponly'] = config.session_cookie_httponly
    extra_options['secure'] = config.session_cookie_secure

    response.set_cookie(config.lang_cookie_name, value=lang, **extra_options)

    return response
