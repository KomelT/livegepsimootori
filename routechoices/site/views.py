import arrow
from allauth.account.forms import LoginForm
from allauth.account.models import EmailAddress
from allauth.account.views import LoginView
from curl_cffi import requests
from django.conf import settings
from django.contrib import auth, messages
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.csrf import csrf_exempt
from django_hosts.resolvers import reverse
from django.utils.timezone import now

from routechoices.core.models import Club, Event, FrontPageFeedback
from routechoices.lib.streaming_response import StreamingHttpRangeResponse
from routechoices.lib.s3 import serve_image_from_s3
from routechoices.site.forms import ContactForm


def home_page(request):
    return redirect(reverse("site:landing_page", host="www"), permanent=True)


def handle_alt_club_url(request, club_slug, path):
    club = Club.objects.filter(slug__iexact=club_slug).first()
    if not club:
        raise Http404()

    if path == "logo":
        if not club.logo:
            raise Http404()
        return serve_image_from_s3(
            request,
            club.logo,
            f"{club.name} Logo",
            default_mime="image/webp",
        )

    return redirect(
        f"//{club_slug}.{settings.PARENT_HOST}/{path}?{request.GET.urlencode()}"
    )


def landing_page(request):
    club_featured = Club.objects.filter(frontpage_featured=True).order_by("?")
    feedbacks = FrontPageFeedback.objects.order_by("?")[:8]
    return render(
        request,
        "site/home.html",
        {"club_featured": club_featured, "user_feedbacks": feedbacks},
    )


def site_favicon(request, icon_name, **kwargs):
    icon_info = {
        "favicon.ico": {"size": 32, "format": "ICO", "mime": "image/x-icon"},
        "apple-touch-icon.png": {"size": 180, "format": "PNG", "mime": "image/png"},
        "icon-192.png": {"size": 192, "format": "PNG", "mime": "image/png"},
        "icon-512.png": {"size": 512, "format": "PNG", "mime": "image/png"},
    }.get(icon_name)
    with open(f"{settings.BASE_DIR}/static_assets/{icon_name}", "rb") as fp:
        data = fp.read()
    return StreamingHttpRangeResponse(request, data, content_type=icon_info["mime"])


def pricing_page(request):
    return render(
        request,
        "site/pricing.html",
    )


@csrf_exempt
def pay_view(request):
    if request.method != "POST":
        return redirect(reverse("site:pricing_view", host="www"))
    yearly_payment = request.POST.get("per-year", False) == "on"
    variants = settings.LEMONSQUEEZY_PRODUCTS_VARIANTS
    variant_id = variants[1] if yearly_payment else variants[0]
    body = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "product_options": {
                    "enabled_variants": [variant_id],
                },
                "checkout_options": {
                    "embed": True,
                    "desc": False,
                    "discount": True,
                },
                "preview": False,
                "expires_at": arrow.utcnow().shift(hours=1).isoformat(),
            },
            "relationships": {
                "store": {
                    "data": {"type": "stores", "id": settings.LEMONSQUEEZY_STORE_ID}
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": variant_id,
                    }
                },
            },
        }
    }
    if club_slug := request.POST.get("club"):
        body["data"]["attributes"]["checkout_data"] = {"custom": {"club": club_slug}}
    r = requests.post(
        "https://api.lemonsqueezy.com/v1/checkouts",
        headers={
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {settings.LEMONSQUEEZY_API_KEY}",
        },
        json=body,
    )
    if r.status_code // 100 == 2:
        data = r.json()
        return redirect(data["data"]["attributes"]["url"])
    1 / 0
    messages.error(request, "Something went wrong!")
    return redirect("/")


def events_view(request):
    event_list = Event.extract_event_lists(request)
    return render(request, "site/event_list.html", event_list)


def contact(request):
    if request.method == "POST" and request.user.is_authenticated:
        form = ContactForm(request.POST)
        if form.is_valid():
            from_email = EmailAddress.objects.get_primary(request.user)
            subject = (
                "Routechoices.com contact form - "
                f'{form.cleaned_data["subject"]} [{from_email}]'
            )
            message = form.cleaned_data["message"]
            msg = EmailMessage(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.EMAIL_CUSTOMER_SERVICE],
                reply_to=[from_email],
            )
            msg.send()
            messages.success(request, "Message sent succesfully")
            return redirect(reverse("site:contact_view", host="www"))
    else:
        form = ContactForm()
    return render(request, "site/contact.html", {"form": form})


def robots_txt(request):
    sitemap_url = reverse("site:sitemap.xml", host="www")
    return HttpResponse(
        f"Sitemap: {request.scheme}:{sitemap_url}\n", content_type="text/plain"
    )


class CustomLoginForm(LoginForm):
    def get_user(self):
        return self.user


class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = "kagi/login.html"

    @property
    def is_admin(self):
        return self.template_name == "admin/login.html"

    def requires_two_factor(self, user):
        return user.webauthn_keys.exists() or user.totp_devices.exists()

    def form_valid(self, form):
        user = form.get_user()
        if not self.requires_two_factor(user):
            # no keys registered, use single-factor auth
            return super().form_valid(form)

        self.request.session["kagi_pre_verify_user_pk"] = user.pk
        self.request.session["kagi_pre_verify_user_backend"] = user.backend

        verify_url = reverse("kagi:verify-second-factor", host="dashboard")
        redirect_to = self.request.POST.get(
            auth.REDIRECT_FIELD_NAME,
            self.request.GET.get(auth.REDIRECT_FIELD_NAME, ""),
        )
        params = {}
        if url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts=[self.request.get_host()],
            require_https=True,
        ):
            params[auth.REDIRECT_FIELD_NAME] = redirect_to
        if self.is_admin:
            params["admin"] = 1
        if params:
            verify_url += "?" + urlencode(params)

        return HttpResponseRedirect(verify_url)

    def get_context_data(self, **kwargs):
        signup_url = self.passthrough_next_url(
            reverse("account_signup", host="dashboard")
        )
        site = get_current_site(self.request)
        ret = super(LoginView, self).get_context_data(**kwargs)
        ret.update(
            {
                "signup_url": signup_url,
                "site": site,
                "SOCIALACCOUNT_ENABLED": False,
                "SOCIALACCOUNT_ONLY": False,
                "LOGIN_BY_CODE_ENABLED": False,
                "PASSKEY_LOGIN_ENABLED": False,
                auth.REDIRECT_FIELD_NAME: self.request.GET.get(
                    auth.REDIRECT_FIELD_NAME, ""
                ),
            }
        )
        ret.update(self.kwargs.get("extra_context", {}))
        return ret


class CustomAdminLoginView(CustomLoginView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_active and not request.user.is_staff:
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


def registration_view(request):
    if not getattr(settings, "PUBLIC_REGISTRATION_ENABLED", True):
        raise Http404()

    events = (
        Event.objects.select_related("club")
        .filter(open_registration=True, end_date__gt=now())
        .order_by(
            "start_date",
            "end_date",
            "name",
        )
    )
    return render(
        request,
        "site/registration.html",
        {"events": events},
    )
