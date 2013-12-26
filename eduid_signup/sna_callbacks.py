import datetime

from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

from eduid_am.tasks import update_attributes


def create_or_update(request, provider, provider_user_id, attributes):
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

    except request.userdb.UserDoesNotExist:
        am_user_exists = None

    if user is None and not am_user_exists:
        # The user is new, is not registered in signup or am either
        # then, register as usual
        user_id = request.db.registered.save({
            provider_key: provider_user_id,
            "email": attributes["email"],
            "date": datetime.datetime.utcnow(),
            "verified": True,
            "displayName": attributes["screen_name"],
            "givenName": attributes["first_name"],
            "sn": attributes["last_name"],
        }, safe=True)

    elif not am_user_exists:
        # If the user is registered in signup but was not propagated to
        # eduid_am
        # Then, update local attributes and continue as new user
        #
        request.db.registered.find_and_modify({
            "email": attributes['email'],
            "verified": False
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
    else:
        # The user is registered in the eduid_am
        # Show a message "email already registered"
        return HTTPFound(location=request.route_url('email_already_registered'))

    user_id = str(user_id)

    # Send the signal to the attribute manager so it can update
    # this user's attributes in the IdP
    update_attributes.delay('eduid_signup', user_id)

    # TODO
    # Should add spinner here to make sure we can read back the user using eduid_am
    # before proceeding. If the attribute manager is not working allright the user will
    # be sent to dashboard using auth_token link below, but dashboard won't find the user.

    # Create an authenticated session and send the user to the
    # success screeen
    remember_headers = remember(request, user_id)

    request.session["email"] = attributes["email"]

    raise HTTPFound(request.route_url('sna_account_created'),
                    headers=remember_headers)


def google_callback(request, user_id, attributes):
    return create_or_update(request, 'google', user_id, attributes)


def facebook_callback(request, user_id, attributes):
    return create_or_update(request, 'facebook', user_id, attributes)


def liveconnect_callback(request, user_id, attributes):
    return create_or_update(request, 'liveconnect', user_id, attributes)
