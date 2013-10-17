from uuid import uuid4
from hashlib import sha256
import datetime

from pyramid.httpexceptions import HTTPInternalServerError

from eduid_signup.i18n import TranslationString as _

from eduid_signup.compat import text_type


def generate_verification_link(request):
    code = text_type(uuid4())
    link = request.route_url("email_verification_link", code=code)
    return (link, code)


def verificate_code(collection, code):
    result = collection.find_and_modify(
        {
            "code": code,
            "verified": False
        }, {
            "$set": {
                "verified": True,
                "verified_ts": datetime.utcnow(),
            }
        },
        new=True,
        safe=True
    )

    if result is None:
        raise HTTPInternalServerError(_("Your email can't be verified now, "
                                      "try it later"))
    return True


def check_email_status(db, email):
    """
        Check the email registration status.

        If the email doesn't exist in database, then return 'new'.

        If exists and it hasn't been verified, then return 'not_verified'.

        If exists and it has been verified before, then return 'verified'.
    """

    email = db.registered.find_one({'email': email})
    if not email:
        return 'new'
    if email.get('verified', False):
        return 'verified'
    else:
        return 'not_verified'


def generate_auth_token(shared_key, email, nonce, timestamp, generator=sha256):
    """
        The shared_key is a secret between the two systems
        The public word must must go through form POST or GET
    """
    return generator("{0}|{1}|{2}|{3}".format(
        shared_key, email, nonce, timestamp)).hexdigest()
