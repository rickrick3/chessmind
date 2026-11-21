from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import services
from .forms import LoginForm, SignupForm


def _next_url(request, default: str = "/learn/") -> str:
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return default


def _with_language(response, lang: str):
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=365 * 24 * 3600)
    return response


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        services.signup_user(request, email=d["email"], password=d["password"], display_name=d["display_name"],
                             timezone=d["timezone"])
        return _with_language(redirect(_next_url(request)), request.learner.language)
    return render(request, "accounts/signup.html", {"form": form, "next": _next_url(request, "")})


def login_view(request):
    form = LoginForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        email, ip = form.cleaned_data["email"], request.META.get("REMOTE_ADDR", "")
        if services.login_blocked(email, ip):
            error = _("Too many attempts. Try again in 15 minutes.")
        else:
            user = authenticate(request, username=email, password=form.cleaned_data["password"])
            if user is None:
                services.record_login_failure(email, ip)
                error = _("Wrong email or password.")
            else:
                services.clear_login_failures(email, ip)
                learner = services.login_user(request, user)
                return _with_language(redirect(_next_url(request)), learner.language)
    return render(request, "accounts/login.html", {"form": form, "error": error, "next": _next_url(request, "")})


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("/")
