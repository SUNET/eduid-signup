from datetime import datetime

from pyramid.renderers import render

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from eduid_am.tasks import update_attributes

from eduid_signup.utils import generate_verification_link, generate_eppn

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

    eppn = generate_eppn(request)
    result = request.db.registered.find_and_modify(
        query={
            'email': email,
        }, update={
            '$set': {
                "subject": "physical person",
                "eduPersonPrincipalName": eppn,
                "email": email,
                "created_ts": datetime.utcnow(),
                "code": code,
                "verified": False,
            },
        }, upsert=True, full_response=True, new=True, safe=True)

    user_id = result.get("value", {}).get("_id")

    logger.info("New user {!s}/{!s} created. e-mail pending confirmation: {!s}".format(
        eppn, user_id, email,
    ))

    if request.registry.settings.get("development", '') != 'true':
        mailer.send(message)
    else:
        # Development
        logger.debug("Confirmation e-mail:\nFrom: {!s}\nTo: {!s}\nSubject: {!s}\n\n{!s}".format(
            message.sender, message.recipients, message.subject, message.body))

    # XXX REMOVE THIS? otherwise users appear in eduid_am without 'passwords'
    # so they can't log in but exceptions are logged in the IdP when they try

    # Send the signal to the attribute manager so it can update
    # this user's attributes in the IdP
    update_attributes.delay('eduid_signup', str(user_id))


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
