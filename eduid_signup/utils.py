from uuid import uuid4
from hashlib import sha256
import datetime
from eduid_signup.compat import text_type

import os
import struct
import proquint
from pyramid.httpexceptions import HTTPServerError

import logging
logger = logging.getLogger(__name__)


class AlreadyVerifiedException(Exception):
    pass


class CodeDoesNotExists(Exception):
    pass


def generate_verification_link(request):
    code = text_type(uuid4())
    link = request.route_url("email_verification_link", code=code)
    return (link, code)


def verify_email_code(request, collection, code):
    status = collection.find_one({
        'code': code,
    })

    if status is None:
        logger.debug("Code {!r} not found in database".format(code))
        raise CodeDoesNotExists()
    else:
        if status.get('verified'):
            logger.debug("Code {!r} already verified".format(code))
            raise AlreadyVerifiedException()

    pending_code = request.session.get('code', None)
    if pending_code is None or code != pending_code:
        logger.debug("Code {!r} (or this sessions code {!r}) does not exist".format(code, pending_code))
        raise CodeDoesNotExists()

    result = collection.update(
        {
            "code": code,
            "verified": False
        }, {
            "$set": {
                "verified": True,
                "verified_ts": datetime.datetime.utcnow(),
            }
        },
        new=True,
        safe=True
    )

    logger.debug("Code {!r} verified : {!r}".format(code, result))
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


def normalize_email(addr):
    return addr.lower()
