from uuid import uuid4

from pyramid.httpexceptions import HTTPInternalServerError


def generate_verification_link(request):
    code = unicode(uuid4())
    link = request.route_url("email_verification_link", code=code)
    return (link, code)


def verificate_code(collection, code):
    result = collection.find_and_modify(
        {
            "code": code,
            "verified": False
        }, {
            "$set": {
                "verified": True
            }
        },
        new=True,
        safe=True
    )

    if result is None:
        raise HTTPInternalServerError("Your email can't be verified now, try"
                                      " it later")
    return True
