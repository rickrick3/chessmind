from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from games.chesscom import ChessComUnavailable

from . import services
from .forms import ChessComForm, LoginForm, SettingsForm, SignupForm


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


def settings_view(request):
    learner = services.ensure_learner(request)
    initial = {"display_name": learner.display_name, "language": learner.language,
               "daily_goal_xp": learner.daily_goal_xp, "timezone": learner.timezone}
    form = SettingsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        services.update_settings(learner, **form.cleaned_data)
        messages.success(request, _("Settings saved."))
        return _with_language(redirect("settings"), learner.language)
    return render(request, "accounts/settings.html", {"form": form})


def chesscom_link(request):
    learner = services.ensure_learner(request)
    form = ChessComForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["username"].strip().lower()
        try:
            services.link_chesscom(learner, name)
            return redirect("game_list")
        except services.UnknownChessComUser:
            error = _("No Chess.com player named “%(name)s”.") % {"name": name}
        except ChessComUnavailable:
            error = _("Chess.com is not answering, try again in a minute.")
    return render(request, "accounts/chesscom.html", {"form": form, "error": error})


@require_POST
def chesscom_unlink(request):
    learner = services.ensure_learner(request)
    services.unlink_chesscom(learner)
    return redirect("chesscom_link")


def delete_account(request):
    learner = services.ensure_learner(request)
    error = None
    if request.method == "POST":
        if learner.is_guest or learner.user.check_password(request.POST.get("password", "")):
            services.delete_account(request)
            return redirect("/")
        error = _("Wrong password.")
    return render(request, "accounts/delete.html", {"error": error})


class PasswordChangeView(LoginRequiredMixin, auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("settings")

    def form_valid(self, form):
        messages.success(self.request, _("Password changed."))
        return super().form_valid(form)
