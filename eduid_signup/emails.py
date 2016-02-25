from pyramid.renderers import render

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from eduid_signup.config import pyramid_unpack_config
from eduid_signup.utils import generate_verification_link, generate_eppn

from eduid_userdb.signup import SignupUser
import eduid_userdb

import logging
logger = logging.getLogger(__name__)


def send_verification_mail(request, email):
    """
    Send a verification code to someone's email address.

    :param request: Pyramid request
    :param email: Email address

    :type request: pyramid.request.Request
    :return:
    """
    config = pyramid_unpack_config(request)

    mailer = get_mailer(request)
    (verification_link, code) = generate_verification_link(request)
    _ = request.translate

    context = {
        "email": email,
        "verification_link": verification_link,
        "site_url": request.route_url("home"),
        "site_name": config.site_name,
        "code": code,
        "verification_code_form_link": request.route_url("verification_code_form"),
    }

    message = Message(
        subject=_("eduid-signup verification email"),
        sender=config.mail_default_sender,
        recipients=[email],
        body=render(
            "templates/verification_email.txt.jinja2",
            context,
            request,
        ),
        html=render(
            "templates/verification_email.html.jinja2",
            context,
            request,
        ),
    )

    signup_user = request.signup_db.get_user_by_pending_mail_address(email)
    if not signup_user:
        mailaddress = eduid_userdb.mail.MailAddress(email = email,
                                                    application = 'signup',
                                                    verified = False,
                                                    primary = True,
                                                    verification_code = code,
                                                    )
        signup_user = SignupUser(eppn = generate_eppn(request))
        signup_user.pending_mail_address = mailaddress
        request.signup_db.save(signup_user)
        logger.info("New user {!s}/{!s} created. e-mail is pending confirmation.".format(signup_user, email))
    else:
        # update mailaddress on existing user with new code
        signup_user.pending_mail_address.verification_code = code
        request.signup_db.save(signup_user)
        logger.info("User {!s}/{!s} updated with new e-mail confirmation code".format(signup_user, email))

    if not config.development:
        mailer.send(message)
    else:
        # Development
        logger.debug("Confirmation e-mail:\nFrom: {!s}\nTo: {!s}\nSubject: {!s}\n\n{!s}".format(
            message.sender, message.recipients, message.subject, message.body))


def send_credentials(request, email, password):
    """
    Send user credentials to new user in e-mail.

    :param request: Pyramid request
    :param email: E-mail address
    :param password: Plaintext password

    :type request: pyramid.request.Request

    :return:
    """
    config = pyramid_unpack_config(request)
    _ = request.translate
    mailer = get_mailer(request)
    context = {
        "email": email,
        "password": password,
        "site_url": request.route_url("home"),
        "site_name": config.site_name,
    }
    message = Message(
        subject=_("eduid-signup credentials"),
        sender=config.mail_default_sender,
        recipients=[email],
        body=render(
            "templates/credentials_email.txt.jinja2",
            context,
            request,
        ),
        html=render(
            "templates/credentials_email.html.jinja2",
            context,
            request,
        ),
    )
    logger.info("Credentials e-mail sent to {!s}".format(email))
    if not config.development:
        mailer.send(message)
    else:
        # Development
        logger.debug("Credentials e-mail:\nFrom: {!s}\nTo: {!s}\nSubject: {!s}\n\n{!s}".format(
            message.sender, message.recipients, message.subject, message.body))
