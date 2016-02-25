from pwgen import pwgen
from re import findall

import vccs_client

import logging
logger = logging.getLogger(__name__)


def generate_password(config, credential_id, user):
    """
    Generate a new password credential and add it to the VCCS authentication backend.

    The salt returned needs to be saved for use in subsequent authentications using
    this password. The password is returned so that it can be conveyed to the user.

    :param config: eduid application configuration
    :param credential_id: VCCS credential_id as string
    :param user: user data as dict

    :type config: eduid_signup.SignupConfig
    :type credential_id: str | unicode
    :type user: eduid_userdb.signup.SignupUser

    :return: (password, salt) both strings
    """
    user_id = str(user.user_id)
    password = pwgen(config.password_length, no_capitalize = True, no_symbols = True)
    factor = vccs_client.VCCSPasswordFactor(password, credential_id)
    logger.debug("Adding VCCS password factor for user {!r}, credential_id {!r}".format(user_id, credential_id))

    vccs = vccs_client.VCCSClient(base_url = config.vccs_url)
    try:
        result = vccs.add_credentials(user_id, [factor])
    except vccs_client.VCCSClientHTTPError as e:
        logger.error(e)
        raise e
    logger.debug("VCCS password (id {!r}) creation result: {!r}".format(credential_id, result))

    return _human_readable(password), factor.salt


def _human_readable(password):
    """
    Format a random password more readable to humans (groups of four characters).

    :param password: string
    :return: readable password as string
    :rtype: string
    """
    regexp = '.{,4}'
    parts = findall(regexp, password)
    return ' '.join(parts).rstrip()
