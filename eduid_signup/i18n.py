from eduid_signup.config import pyramid_unpack_config

from pyramid.i18n import TranslationStringFactory, get_localizer

translation_domain = 'eduid_signup'
TranslationString = TranslationStringFactory(translation_domain)


def locale_negotiator(request):
    """
    Choose language for XXX

    :param request: Pyramid request
    :type request: pyramid.request.Request

    :return: Locale name
    :rtype: unicode
    """
    config = pyramid_unpack_config(request)
    available_languages = config.available_languages.keys()

    cookie_lang = request.cookies.get(config.lang_cookie_name, None)
    if cookie_lang and cookie_lang in available_languages:
        return cookie_lang

    locale_name = request.accept_language.best_match(available_languages)

    if locale_name not in available_languages:
        locale_name = config.default_locale_name
    return unicode(locale_name)


def add_localizer(event):
    request = event.request
    localizer = get_localizer(request)

    def auto_translate(string):
        return localizer.translate(TranslationString(string))

    request.localizer = localizer
    request.translate = auto_translate
