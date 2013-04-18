from uuid import uuid4


def generate_verification_link(request):
    code = unicode(uuid4())
    link = request.route_url("email_verification_link", code=code)
    return (link, code)


def verificate_link(db, link):
    pass
