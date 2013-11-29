from pwgen import pwgen
from re import findall

import vccs_client


def generate_password(settings, credential_id, user):
    """
    Generate a new password credential and add it to the VCCS authentication backend.

    The salt returned needs to be saved for use in subsequent authentications using
    this password. The password is returned so that it can be conveyed to the user.

    :param settings: settings dict
    :param credential_id: VCCS credential_id as string
    :param user: user data as dict
    :return: (password, salt) both strings
    """
    password = pwgen(settings.get('password_length'), no_capitalize = True, no_symbols = True)
    factor = vccs_client.VCCSPasswordFactor(password, credential_id)
    vccs = vccs_client.VCCSClient(base_url = settings.get('vccs_url'))
    vccs.add_credentials(user['_id'], [factor])

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
    return ' '.join(parts)
