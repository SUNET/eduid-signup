from datetime import datetime

from pyramid.renderers import render

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from eduid_am.tasks import update_attributes

from eduid_signup.utils import generate_verification_link, generate_eppn

from eduid_signup.user import SignupUser
import eduid_userdb

import logging
logger = logging.getLogger(__name__)


def send_verification_mail(request, email):
    mailer = get_mailer(request)
    (verification_link, code) = generate_verification_link(request)
    _ = request.translate

    context = {
        "email": email,
        "verification_link": verification_link,
        "site_url": request.route_url("home"),
        "site_name": request.registry.settings.get("site.name", "eduid_signup"),
        "code": code,
        "verification_code_form_link": request.route_url("verification_code_form"),
    }

    message = Message(
        subject=_("eduid-signup verification email"),
        sender=request.registry.settings.get("mail.default_sender"),
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

    signup_user = request.db.get_user_by_pending_mail_address(email)
    if not signup_user:
        mailaddress = eduid_userdb.mail.MailAddress(email = email,
                                                    application = 'signup',
                                                    verified = False,
                                                    primary = True,
                                                    verification_code = code,
                                                    )
        signup_user = SignupUser(eppn = generate_eppn(request))
        signup_user.pending_mail_address = mailaddress
        request.db.save(signup_user)
        logger.info("New user {!s}/{!s} created. e-mail is pending confirmation.".format(signup_user, email))
    else:
        # update mailaddress on existing user with new code
        signup_user.pending_mail_addresses.verification_code = code
        request.db.save(signup_user)
        logger.info("User {!s}/{!s} updated with new e-mail confirmation code".format(signup_user, email))

    if request.registry.settings.get("development", '') != 'true':
        mailer.send(message)
    else:
        # Development
        logger.debug("Confirmation e-mail:\nFrom: {!s}\nTo: {!s}\nSubject: {!s}\n\n{!s}".format(
            message.sender, message.recipients, message.subject, message.body))


def send_credentials(request, email, password):
    _ = request.translate
    mailer = get_mailer(request)
    context = {
        "email": email,
        "password": password,
        "site_url": request.route_url("home"),
        "site_name": request.registry.settings.get("site.name", "eduid_signup"),
    }
    message = Message(
        subject=_("eduid-signup credentials"),
        sender=request.registry.settings.get("mail.default_sender"),
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
    if request.registry.settings.get("development", '') != 'true':
        mailer.send(message)
    else:
        # Development
        logger.debug("Credentials e-mail:\nFrom: {!s}\nTo: {!s}\nSubject: {!s}\n\n{!s}".format(
            message.sender, message.recipients, message.subject, message.body))
