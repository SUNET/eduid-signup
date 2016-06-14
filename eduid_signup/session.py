from zope.interface import implementer
from pyramid.interfaces import ISessionFactory, ISession
from eduid_common.session.pyramid_session import SessionFactory as CommonSessionFactory
from eduid_common.session.pyramid_session import Session as CommonSession

import logging
logger = logging.getLogger(__name__)


_EDIT_USER_EPPN = 'edit-user_eppn'
_USER_EPPN = 'user_eppn'


Session = implementer(ISession)(CommonSession)


@implementer(ISessionFactory)
class SessionFactory(CommonSessionFactory):
    '''
    Session factory implementing the pyramid.interfaces.ISessionFactory
    interface.
    It uses the SessionManager defined in eduid_common.session.session
    to create sessions backed by redis.
    '''

    def __call__(self, request):
        '''
        Create a session object for the given request.

        :param request: the request
        :type request: pyramid.request.Request

        :return: the session
        :rtype: Session
        '''
        self.request = request
        settings = request.registry.settings
        session_name = settings.get('session.key')
        cookies = request.cookies
        token = cookies.get(session_name, None)
        if token is not None:
            try:
                base_session = self.manager.get_session(token=token)
                existing_session = Session(request, base_session)
                return existing_session
            except KeyError:  # No session data found
                pass
        base_session = self.manager.get_session(data={})
        base_session['flash_messages'] = {'default': []}
        base_session.commit()
        session = Session(request, base_session, new=True)
        session.set_cookie()
        return session
