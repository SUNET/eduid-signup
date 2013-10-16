import datetime

from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

from eduid_am.tasks import update_attributes


def create_or_update(request, provider, provider_user_id, attributes):
    provider_key = '%s_id' % provider
    # Create or update the user
    user = request.db.users.find_one({provider_key: provider_user_id})
    if user is None:  # first time
        register = request.db.registered.find_one({"email": attributes["email"]})
        if register is None:
            user_id = request.db.registered.insert({
                provider_key: provider_user_id,
                "email": attributes["email"],
                "date": datetime.datetime.utcnow(),
                "verified": True,
                "displayName": attributes["screen_name"],
                "givenName": attributes["first_name"],
                "sn": attributes["last_name"],
            }, safe=True)
        elif not register['verified']:
            request.db.registered.find_and_modify({
                "email": attributes['email'],
                "verified": False
            }, {
                "$set": {
                    "verified": True,
                    "displayName": attributes["screen_name"],
                    "givenName": attributes["first_name"],
                    "sn": attributes["last_name"],
                }
            })
            user_id = register['_id']
        else:
            # TODO
            # The user is already registered and his email was verified.
            # Maybe, we want to warm him and send to a view to change his password
            # or edit his profile
            user_id = register['_id']
    else:
        user_id = user['_id']

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
