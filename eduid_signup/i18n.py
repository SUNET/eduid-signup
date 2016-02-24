from pyramid.i18n import TranslationStringFactory, get_localizer

translation_domain = 'eduid_signup'
TranslationString = TranslationStringFactory(translation_domain)


def locale_negotiator(request):
    settings = request.registry.settings
    available_languages = settings['available_languages'].keys()
    cookie_name = settings['lang_cookie_name']

    cookie_lang = request.cookies.get(cookie_name, None)
    if cookie_lang and cookie_lang in available_languages:
        return cookie_lang

    locale_name = request.accept_language.best_match(available_languages)

    if locale_name not in available_languages:
        locale_name = settings['default_locale_name']
    return locale_name


def add_localizer(event):
    request = event.request
    localizer = get_localizer(request)

    def auto_translate(string):
        return localizer.translate(TranslationString(string))

    request.localizer = localizer
    request.translate = auto_translate
