from datetime import datetime

from pyramid.renderers import render

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from eduid_signup.i18n import TranslationString as _
from eduid_signup.utils import generate_verification_link


def send_verification_mail(request, email):
    mailer = get_mailer(request)
    (verification_link, code) = generate_verification_link(request)

    message = Message(
        subject=_("eduid-signup verification email"),
        sender=request.registry.settings.get("mail_default_sender"),
        recipients=[email],
        body=render(
            "templates/verification_email.txt.jinja2",
            {
                "email": email,
                "verification_link": verification_link,
                "site_url": "http://example.com/",
                "site_name": "Site Name"
            },
            request
        )
    )

    mailer.send(message)

    request.db.registered.insert({
        "email": email,
        "date": datetime.utcnow(),
        "code": code,
    })
