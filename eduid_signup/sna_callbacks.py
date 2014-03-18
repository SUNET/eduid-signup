import datetime

from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

from eduid_am.tasks import update_attributes
from eduid_signup.utils import generate_eppn, normalize_email


def create_or_update_sna(request):

    provider = request.session['provider']
    provider_user_id = request.session['provider_user_id']
    attributes = request.session['social_info']

    provider_key = '%s_id' % provider

    user = request.db.registered.find_one({
        "email": attributes['email'],
        "verified": True
    })

    try:
        am_user_exists = request.userdb.exists_by_filter({
            'mailAliases': {
                '$elemMatch': {
                    'email': attributes["email"],
                    'verified': True
                }
            }
        })

    except request.userdb.exceptions.UserDoesNotExist:
        am_user_exists = None

    if user is None and not am_user_exists:
        # The user is new, is not registered in signup or am either
        # then, register as usual
        eppn = generate_eppn(request)
        user_id = request.db.registered.save({
            provider_key: provider_user_id,
            "email": attributes["email"],
            "date": datetime.datetime.utcnow(),
            "verified": True,
            "displayName": attributes["screen_name"],
            "givenName": attributes["first_name"],
            "sn": attributes["last_name"],
            "eduPersonPrincipalName": eppn,
        }, safe=True)

    elif not am_user_exists:
        # If the user is registered in signup but was not propagated to
        # eduid_am
        # Then, update local attributes and continue as new user
        #
        request.db.registered.find_and_modify({
            "email": attributes['email'],
            "verified": True
        }, {
            "$set": {
                provider_key: provider_user_id,
                "verified": True,
                "displayName": attributes["screen_name"],
                "givenName": attributes["first_name"],
                "sn": attributes["last_name"],
            }
        })
        user_id = user['_id']

    user_id = str(user_id)

    # Send the signal to the attribute manager so it can update
    # this user's attributes in the IdP
    update_attributes.delay('eduid_signup', user_id)

    # Create an authenticated session and send the user to the
    # success screeen

    request.session["email"] = attributes["email"]
    return user_id


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
