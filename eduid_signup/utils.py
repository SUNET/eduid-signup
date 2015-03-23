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


def verify_email_code(collection, code):
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


def check_email_status(userdb, email):
    """
        Check the email registration status.

        If the email doesn't exist in database, then return 'new'.

        If exists and it hasn't been verified, then return 'not_verified'.

        If exists and it has been verified before, then return 'verified'.
    """
    try:
        am_user = userdb.get_user_by_email(email)
    except userdb.exceptions.UserDoesNotExist:
        return 'new'
    emails = am_user.get_mail_aliases()
    for mail in emails:
        if mail.get('email', '') == email and mail.get('verified', False):
            return 'verified'
    return 'not_verified'


def generate_auth_token(shared_key, email, nonce, timestamp, generator=sha256):
    """
        The shared_key is a secret between the two systems
        The public word must must go through form POST or GET
    """
    logger.debug("Generating auth-token for user {!r}, nonce {!r}, ts {!r}".format(email, nonce, timestamp))
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
            request.userdb.get_user_by_eppn(eppn)
        except request.userdb.exceptions.UserDoesNotExist:
            return eppn
    raise HTTPServerError()


def normalize_email(addr):
    return addr.lower()


def record_tou(request, user_id, source):
    """
    Record user acceptance of terms of use.

    :param request: The request
    :type request: Request
    :param user_id: the _id of the user that has accepted the ToU
    :type user_id: ObjectId
    :param source: An identificator for the proccess during which the user has accepted the ToU (e.g., "signup")
    :type source: str
    """
    logger.debug('Recording ToU acceptance for user {!r} (source: {!r})'.format(user_id, source))
    tou_version = request.registry.settings['tou_version']
    request.toudb.consent.update(
        {'_id': user_id},
        {'$push': {
            'eduid_ToU': {
                tou_version: {
                    'ts': datetime.datetime.utcnow(),
                    'source': source
                }
            }
        }}
        , safe=True, upsert=True)
