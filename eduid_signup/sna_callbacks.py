from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

from eduid_am.tasks import update_attributes
from eduid_signup.utils import generate_eppn, normalize_email

from eduid_signup.user import SignupUser
import eduid_userdb

import logging
logger = logging.getLogger(__name__)


def create_or_update_sna(request, social_info):
    """

    :param request:
    :param social_info: Information from Social network login provider

    :type social_info: dict
    :return:
    """
    provider = request.session['provider']
    provider_user_id = request.session['provider_user_id']

    logging.debug("create_or_update_sna called for {!r}+{!r}".format(provider, provider_user_id))

    signup_user = request.signup_db.get_user_by_pending_mail_address(social_info['email'])
    logger.debug("Signup user from pending e-mail address {!r}: {!r}".format(social_info['email'], signup_user))

    if signup_user is None:
        # The user doesn't exist at all in the signup_userdb.
        signup_user = SignupUser(eppn = generate_eppn(request))
    else:
        # If the user is registered in signup but was not propagated to
        # eduid_am, update with data from the Social network (below)
        assert isinstance(signup_user, SignupUser)
        signup_user.pending_mail_address = None

    mailaddress = eduid_userdb.mail.MailAddress(email=social_info['email'],
                                                application='signup (using {!s})'.format(provider),
                                                verified=True,
                                                primary=True,
                                                )
    signup_user.mail_addresses.add(mailaddress)

    signup_user.display_name = social_info['screen_name']
    signup_user.given_name = social_info['first_name']
    signup_user.surname = social_info['last_name']
    signup_user.subject = 'physical person'

    signup_user.social_network = provider
    signup_user.social_network_id = provider_user_id

    logging.debug("Saving social signed up user {!s} (e-mail {!s}) to signup userdb".format(
        signup_user, signup_user.mail_addresses.primary.email))
    res = request.signup_db.save(signup_user)
    logging.debug("Save result: {!r}".format(res))

    # Send the signal to the attribute manager so it can update
    # this user's attributes in the central eduID UserDB
    #update_attributes.delay('eduid_signup', signup_user.user_id)

    # Create an authenticated session and send the user to the
    # success screeen (use sanitized address)
    request.session['email'] = signup_user.mail_addresses.primary.email


def save_data_in_session(request, provider, provider_user_id, attributes):

    remember_headers = remember(request, provider_user_id)

    if 'email' in attributes:
        attributes['email'] = normalize_email(attributes['email'])

    request.session.update({
        "social_info": attributes,
        "provider": provider,
        "provider_user_id": provider_user_id,
    })

    raise HTTPFound(request.route_url('review_fetched_info'),
                    headers=remember_headers)


def google_callback(request, user_id, attributes):
    return save_data_in_session(request, 'google', user_id, attributes)
    #return create_or_update(request, 'google', user_id, attributes)


def facebook_callback(request, user_id, attributes):
    return save_data_in_session(request, 'facebook', user_id, attributes)
    #return create_or_update(request, 'facebook', user_id, attributes)


def liveconnect_callback(request, user_id, attributes):
    return save_data_in_session(request, 'liveconnect', user_id, attributes)
    #return create_or_update(request, 'liveconnect', user_id, attributes)
