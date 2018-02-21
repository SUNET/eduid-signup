import bson
from uuid import uuid4
from hashlib import sha256
import datetime
from eduid_signup.compat import text_type
from eduid_userdb.tou import ToUEvent
from eduid_userdb import MailAddress

import os
import struct
import proquint
import requests
import time
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


def verify_email_code(signup_db, code):
    """
    Look up a user in the signup userdb using an e-mail verification code.

    Mark the e-mail address as confirmed, save the user and return the user object.

    :param signup_db: Signup user database
    :param code: Code as received from user
    :type signup_db: SignupUserDb
    :type code: str | unicode

    :return: Signup user object
    :rtype: SignupUser
    """
    signup_user = signup_db.get_user_by_mail_verification_code(code)

    if not signup_user:
        logger.debug("Code {!r} not found in database".format(code))
        raise CodeDoesNotExists()

    mail = MailAddress(data=signup_user.pending_mail_address.to_dict(), raise_on_unknown=False)
    if mail.is_verified:
        # There really should be no way to get here, is_verified is set to False when
        # the EmailProofingElement is created.
        logger.debug("Code {!r} already verified ({!s})".format(code, mail))
        raise AlreadyVerifiedException()

    mail.is_verified = True
    mail.verified_ts = True
    mail.verified_by = 'signup'
    mail.is_primary = True
    signup_user.pending_mail_address = None
    signup_user.mail_addresses.add(mail)
    result = signup_db.save(signup_user)

    logger.debug("Code {!r} verified and user {!s} saved: {!r}".format(code, signup_user, result))
    return signup_user


def check_email_status(userdb, signup_db, email):
    """
    Check the email registration status.

    If the email doesn't exist in database, then return 'new'.

    If exists and it hasn't been verified, then return 'not_verified'.

    If exists and it has been verified before, then return 'verified'.

    :param userdb: eduID central userdb
    :param signup_db: Signup userdb
    :param email: Address to look for

    :type userdb: eduid_userdb.UserDb
    :type signup_db: eduid_userdb.signup.SignupUserDB
    :type email: str | unicode
    """
    try:
        am_user = userdb.get_user_by_mail(email, raise_on_missing=True, include_unconfirmed=False)
        logger.debug("Found user {!s} with email {!s}".format(am_user, email))
        return 'verified'
    except userdb.exceptions.UserDoesNotExist:
        logger.debug("No user found with email {!s} in eduid userdb".format(email))

    try:
        signup_user = signup_db.get_user_by_pending_mail_address(email)
        if signup_user:
            logger.debug("Found user {!s} with pending email {!s} in signup db".format(signup_user, email))
            return 'not_verified'
    except userdb.exceptions.UserDoesNotExist:
        logger.debug("No user found with email {!s} in signup db either".format(email))

    # Workaround for failed earlier sync of user to userdb: Remove any signup_user with this e-mail address.
    remove_users_with_mail_address(signup_db, email)

    return 'new'


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


def record_tou(request, user, source):
    """
    Record user acceptance of terms of use.

    :param request: The request
    :type request: Request
    :param user: the user that has accepted the ToU
    :type user: eduid_userdb.signup.User
    :param source: An identificator for the proccess during which
                   the user has accepted the ToU (e.g., "signup")
    :type source: str
    """
    event_id = bson.ObjectId()
    created_ts = datetime.datetime.utcnow()
    tou_version = request.registry.settings['tou_version']
    logger.debug('Recording ToU acceptance {!r} (version {!s})'
                 ' for user {!r} (source: {!s})'.format(
                     event_id, tou_version,
                     user.user_id, source))
    user.tou.add(ToUEvent(
        version = tou_version,
        application = source,
        created_ts = created_ts,
        event_id = event_id
        ))


def remove_users_with_mail_address(signup_db, email):
    """
    Remove all users with a certain (confirmed) e-mail address from signup_db.

    When syncing of signed up users fail, they remain in the signup_db in a completed state
    (no pending mail address). This prevents the user from signing up again, and they can't
    use their new eduid account either since it is not synced to the central userdb.

    An option would have been to sync the user again, now, but that was deemed more
    surprising to the user so instead we remove all the unsynced users from signup_db
    so the user can do a new signup.

    :param signup_db: SignupUserDB
    :param email: E-mail address

    :param signup_db: eduid_userdb.signup.SignupUserDB
    :param email: str | unicode

    :return:
    """
    # The e-mail address does not exist in userdb (checked by caller), so if there exists a user
    # in signup_db with this (non-pending) e-mail address, it is probably left-overs from a
    # previous signup where the sync to userdb failed. Clean away all such users in signup_db
    # and continue like this was a completely new signup.
    completed_users = signup_db.get_user_by_mail(email, raise_on_missing = False, return_list = True)
    for user in completed_users:
        logger.warning('Removing old user {!s} with e-mail {!s} from signup_db'.format(user, email))
        signup_db.remove_user_by_id(user.user_id)


def verify_recaptcha(secret_key, captcha_response, user_ip, retries=3):
    """
    :param secret_key: Recaptcha secret key
    :param captcha_response: User recaptcha response
    :param user_ip: User ip address
    :param retries: Number of times to retry sending recaptcha response

    :type secret_key: str
    :type captcha_response: str
    :type user_ip: str
    :type retries: int

    :return: True|False
    :rtype: bool
    """
    url = 'https://www.google.com/recaptcha/api/siteverify'
    params = {
        'secret': secret_key,
        'response': captcha_response,
        'remoteip': user_ip
    }

    for i in range(0, retries):
        try:
            logger.debug('Sending the CAPTCHA user response to google')
            verify_rs = requests.get(url, params=params, verify=True)
            logger.debug("CAPTCHA response: {}".format(verify_rs))
            verify_rs = verify_rs.json()
            if verify_rs.get('success', False):
                return True
        except requests.exceptions.RequestException as e:
            if i < 2:
                logger.debug('Caught RequestException while sending CAPTCHA, trying again.')
                logger.debug(e)
                time.sleep(0.5)
            else:
                logger.debug('Caught RequestException while sending CAPTCHA, giving up.')
                raise

    logger.debug("Invalid CAPTCHA response from {}: {}".format(user_ip,
                                                               verify_rs.get('error-codes', 'Unspecified error')))
    return False
