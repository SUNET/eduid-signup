from pyramid.view import view_config


@view_config(route_name='home', renderer='string')
def home(request):
    return 'Hello world'
