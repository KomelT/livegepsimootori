from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.signals import user_logged_in, user_signed_up
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme


class SiteAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return getattr(settings, "ACCOUNT_SIGNUP_ENABLED", True)

    def is_safe_url(self, url):
        return url_has_allowed_host_and_scheme(
            url, allowed_hosts=settings.REDIRECT_ALLOWED_DOMAINS
        )

    def get_user_signed_up_signal(self):
        return user_signed_up

    def get_user_logged_in_signal(self):
        return user_logged_in
