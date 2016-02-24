import re

from pyramid.config import Configurator
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPNotFound
from pyramid.i18n import get_locale_name

from eduid_am.celery import celery
from eduid_common.config.parsers import IniConfigParser
from eduid_signup.i18n import locale_negotiator
from eduid_userdb import MongoDB, UserDB
from eduid_userdb.signup import SignupUserDB


def includeme(config):
    # DB setup
    _mongodb_tou = MongoDB(config.registry.settings['mongo_uri'], 'eduid_tou')
    _userdb = UserDB(config.registry.settings['mongo_uri'], 'eduid_am')
    _signup_db = SignupUserDB(config.registry.settings['mongo_uri'], 'eduid_signup')

    # Create mongodb client instance and store it in our config,
    # and make a getter lambda for pyramid to retreive it
    config.registry.settings['signup_db'] = _signup_db
    config.add_request_method(lambda x: x.registry.settings['signup_db'], 'signup_db', reify=True)

    # Create userdb instance and store it in our config,
    # and make a getter lambda for pyramid to retreive it (will be available as 'request.userdb')
    config.registry.settings['userdb'] = _userdb
    config.add_request_method(lambda x: x.registry.settings['userdb'], 'userdb', reify=True)

    # store mongodb tou client instance in our config,
    # and make a getter lambda for pyramid to retreive it
    config.registry.settings['mongodb_tou'] = _mongodb_tou
    config.add_request_method(lambda x: x.registry.settings['mongodb_tou'].get_database(), 'toudb', reify=True)

    # root views
    config.add_route('home', '/')
    config.add_route('help', '/help/')
    config.add_route('success', '/success/')
    config.add_route('email_verification_link', '/email_verification/{code}/')
    config.add_route('sna_account_created', '/sna_account_created/')
    config.add_route('trycaptcha', '/trycaptcha/')
    config.add_route('resend_email_verification', '/resend_email_verification/')
    config.add_route('email_already_registered', '/email_already_registered/')
    config.add_route('verification_code_form', '/verification_code_form/')
    config.add_route('review_fetched_info', '/review_fetched_info/')
    config.add_route('set_language', '/set_language/')

    config.add_route('error500test', '/error500test/')
    config.add_route('error500', '/error500/')

    config.add_route('error404', '/error404/')

    config.set_request_property(get_locale_name, 'locale', reify=True)
    config.add_subscriber('eduid_signup.i18n.add_localizer',
                          'pyramid.events.NewRequest')

    if not config.registry.settings['testing']:
        config.add_view(context=Exception,
                        view='eduid_signup.views.exception_view',
                        renderer='templates/error500.jinja2')
        config.add_view(context=HTTPNotFound,
                        view='eduid_signup.views.exception_view',
                        renderer='templates/error404.jinja2')

    # Favicon
    config.add_route('favicon', '/favicon.ico')
    config.add_view('eduid_signup.views.favicon_view', route_name='favicon')


def add_setting(src, default, dst=None, type_='unicode', required=False):
    if dst is None:
        dst = src
    params = {'type': type_,
              'required': required,
              }
    return src, dst, default, params,


def parse_settings(cfg, parser, settings):
    res = {}
    for (src, dst, default, params) in cfg:
        if src in settings:
            if params.get('type') == 'mapping':
                value = parser.read_mapping(settings, src, default)
            else:
                value = parser.read_setting_from_env(settings, src, default)
            res[dst] = _type_cast(src, value, params)
        else:
            if params.get('required'):
                raise ValueError('Required setting {!r} not set'.format(src))
            res[dst] = default
    return res


def _type_cast(name, value, params):
    try:
        return _type_cast_safe(value, params)
    except Exception as exc:
        raise ValueError('Failed parsing configuration option {!r}: {!s}'.format(name, exc))


def _type_cast_safe(value, params):
    if params['type'] is 'unicode':
        return unicode(value)
    if params['type'] == 'int':
        return int(value)
    if params['type'] == 'bool':
        return asbool(value)
    raise NotImplementedError('Type casting to {!r} not implemented'.format(params['type']))


def main(global_config, **settings_in):
    cp = IniConfigParser('')  # Init without config file as it is already loaded

    cfg = [
        # Required settings
        add_setting('mongo_uri', None, required = True),
        add_setting('profile_link', None, required = True),
        add_setting('dashboard_link', None, required = True),
        add_setting('site.name', 'eduid_signup', required = True),
        add_setting('signup_hostname', None, required = True),
        add_setting('signup_baseurl', None, required = True),
        add_setting('reset_password_link', None, required = True),
        add_setting('vccs_url', None, required = True),
        add_setting('auth_shared_secret', None, required = True),
        add_setting('student_link', None, required = True),
        # add_setting('technicians_link', None, required = True),
        add_setting('staff_link', None, required = True),
        add_setting('faq_link', None, required = True),
        add_setting('privacy_link', None, required = True),
        add_setting('session.cookie_expires', None, required = True, type_ = 'int'),
        add_setting('tou_version', None, required = True),
        add_setting('lang_cookie_domain', None, required = True),

        # Mailer settings
        add_setting('host', 'localhost', dst = 'mail.host'),
        add_setting('port', 25, dst = 'mail.port', type_ = 'int'),
        add_setting('username', None, dst = 'mail.username'),
        add_setting('password', None, dst = 'mail.password'),
        add_setting('default_sender', 'no-reply@example.com', dst = 'mail.default_sender'),

        add_setting('available_languages', {'en': 'English',
                                            'sv': 'Svenska'}, type_ = 'mapping'),
        add_setting('default_locale_name', 'en'),
        add_setting('recaptcha_public_key', ''),
        add_setting('recaptcha_private_key', ''),
        # add_setting('mongo_replicaset', None),
        add_setting('broker_url', 'amqp://'),
        add_setting('celery_result_backend', 'amqp'),
        add_setting('google_callback', 'eduid_signup.sna_callbacks.google_callback'),
        add_setting('facebook_callback', 'eduid_signup.sna_callbacks.facebook_callback'),
        add_setting('liveconnect_callback', 'eduid_signup.sna_callbacks.liveconnect_callback'),
        add_setting('password_length', 10, type_ = 'int'),
        add_setting('account_creation_timeout', 10, type_ = 'int'),
        add_setting('testing', False, type_ = 'bool'),
        add_setting('development', False, type_ = 'bool'),
        add_setting('static_url', None),
        add_setting('httponly', True, dst = 'session.httponly', type_ = 'bool'),
        add_setting('secure', True, dst = 'session.secure', type_ = 'bool'),
        add_setting('lang_cookie_name', 'lang'),
    ]

    settings = parse_settings(cfg, cp, dict(settings_in))

    # configure Celery broker
    celery.conf.update({
        'MONGO_URI': settings['mongo_uri'],
        'BROKER_URL': settings['broker_url'],
        'CELERY_RESULT_BACKEND': settings['celery_result_backend'],
        'CELERY_TASK_SERIALIZER': 'json',
        # Avoid broken connections across firewall by disabling pool
        # http://docs.celeryproject.org/en/latest/configuration.html#broker-pool-limit
        'BROKER_POOL_LIMIT': 0,
    })
    settings['celery'] = celery

    for x in settings_in.keys():
        if not x in settings:
            import sys
            sys.stderr.write("SETTING {!r} NOT FOUND\n".format(x))
            settings[x] = settings_in[x]


    # The configurator is the main object about configuration
    config = Configurator(settings=settings, locale_negotiator=locale_negotiator)

    # include other packages
    config.include('pyramid_beaker')
    config.include('pyramid_jinja2')

    if settings['testing'] or settings['development']:
        config.include('pyramid_mailer.testing')
    else:
        config.include('pyramid_mailer')

    config.include('pyramid_tm')
    config.include('pyramid_sna')

    # global directives
    if settings['static_url']:
        config.add_static_view(settings['static_url'], 'static')
    else:
        config.add_static_view('static', 'static', cache_max_age=3600)

    config.add_translation_dirs('eduid_signup:locale/')

    # eduid specific configuration
    includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])
    return config.make_wsgi_app()
