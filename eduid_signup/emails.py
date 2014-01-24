from datetime import datetime

from pyramid.httpexceptions import HTTPServerError
from pyramid.renderers import render
from pyramid.security import authenticated_userid, remember

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from eduid_am.tasks import update_attributes

from eduid_signup.utils import generate_verification_link

import os
import struct
import proquint


def generate_eppn(request):
    """
    Generate a unique eduPersonPrincipalName.

    Unique is defined as 'at least it doesn't exist right now'.

    :param request:
    :return: eppn
    :rtype: string
    """
    for _ in range(10):
        eppn_int = struct.unpack('I', os.urandom(4))[0]
        eppn = proquint.from_int(eppn_int)
        try:
            request.userdb.get_user_by_attr('eduPersonPrincipalName', eppn)
        except request.userdb.UserDoesNotExist:
            return eppn
    raise HTTPServerError()


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
                "eduPersonPrincipalName": eppn,
                "email": email,
                "created_ts": datetime.utcnow(),
                "code": code,
                "verified": False,
            },
        }, upsert=True, full_response=True, new=True, safe=True)

    user_id = result.get("value", {}).get("_id")

    mailer.send(message)

    # Send the signal to the attribute manager so it can update
    # this user's attributes in the IdP
    update_attributes.delay('eduid_signup', str(user_id))

    user_session = authenticated_userid(request)
    if user_session is not None:
        request.session['code'] = code
        return {}
    else:
        headers = remember(request, user_id)
        request.session['code'] = code
        return headers


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
    mailer.send(message)
