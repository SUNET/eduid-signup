import datetime

from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember


def google_callback(request, user_id, attributes):
    """pyramid_sna calls this function aftera successfull authentication flow"""
    # Create or update the user
    user = request.db.users.find_one({'google_id': user_id})
    if user is None:  # first time
        user_id = request.db.registered.insert({
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


def facebook_callback(request, user_id, attributes):
    pass
