from datetime import datetime

from pyramid.renderers import render

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from eduid_am.tasks import update_attributes

from eduid_signup.i18n import TranslationString as _
from eduid_signup.utils import generate_verification_link


def send_verification_mail(request, email):
    mailer = get_mailer(request)
    (verification_link, code) = generate_verification_link(request)

    context = {
        "email": email,
        "verification_link": verification_link,
        "site_url": request.route_url("home"),
        "site_name": request.registry.settings.get("site.name", "eduid_signup")
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

    result = request.db.registered.find_and_modify(
        query={
            'email': email,
        }, update={
            '$set': {
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
