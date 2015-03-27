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


def verify_email_code(userdb, code):
    """
    Look up a user in the signup userdb using an e-mail verification code.

    Mark the e-mail address as confirmed, save the user and return the user object.

    :param userdb: Signup user database
    :param code: Code as received from user
    :type userdb: SignupUserDb
    :type code: str | unicode

    :return: Signup user object
    :rtype: SignupUser
    """
    signup_user = userdb.get_user_by_mail_verification_code(code)

    if not signup_user:
        logger.debug("Code {!r} not found in database".format(code))
        raise CodeDoesNotExists()

    mail = signup_user.pending_mail_address
    if mail.is_verified:
        logger.debug("Code {!r} already verified ({!s})".format(code, mail))
        raise AlreadyVerifiedException()

    mail.is_verified = True
    mail.verified_ts = True
    mail.verified_by = 'signup'
    mail.is_primary = True
    signup_user.pending_mail_address = None
    signup_user.mail_addresses.add(mail)
    result = userdb.save(signup_user)

    logger.debug("Code {!r} verified and user {!s} saved: {!r}".format(code, signup_user, result))
    return signup_user


def check_email_status(userdb, email):
    """
        Check the email registration status.

        If the email doesn't exist in database, then return 'new'.

        If exists and it hasn't been verified, then return 'not_verified'.

        If exists and it has been verified before, then return 'verified'.
    """
    try:
        am_user = userdb.get_user_by_mail(email, raise_on_missing=True)
        logger.debug("Found user {!s} with email {!s}".format(am_user, email))
    except userdb.exceptions.UserDoesNotExist:
        logger.debug("No user found with email {!s}".format(email))
        return 'new'
    this = am_user.mail_addresses.find(email)
    if this and this.verified:
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
