import datetime

from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember


def create_or_update(request, provider, provider_user_id, attributes):
    provider_key = '%s_id' % provider
    # Create or update the user
    user = request.db.users.find_one({provider_key: provider_user_id})
    if user is None:  # first time
        user_id = request.db.registered.insert({
            provider_key: provider_user_id,
            "email": attributes["email"],
            "date": datetime.datetime.utcnow(),
            "verified": True,
            "screen_name": attributes["screen_name"],
            "first_name": attributes["first_name"],
            "last_name": attributes["last_name"],
        }, safe=True)
    else:
        user_id = user['_id']

    # Create an authenticated session and send the user to the
    # success screeen
    remember_headers = remember(request, str(user_id))
    return HTTPFound(request.route_url('success'), headers=remember_headers)


def google_callback(request, user_id, attributes):
    return create_or_update(request, 'google', user_id, attributes)


def facebook_callback(request, user_id, attributes):
    return create_or_update(request, 'facebook', user_id, attributes)
