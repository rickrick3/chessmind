from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from .services import valid_timezone

User = get_user_model()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class SignupForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    display_name = forms.CharField(label=_("Name (optional)"), max_length=40, required=False)
    timezone = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_email(self):
        email = normalize_email(self.cleaned_data["email"])
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError(_("This email already has an account."))
        return email

    def clean(self):
        data = super().clean()
        email, password = data.get("email"), data.get("password")
        if email and password:
            try:
                validate_password(password, User(username=email, email=email))
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return data


class LoginForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)

    def clean_email(self):
        return normalize_email(self.cleaned_data["email"])


class SettingsForm(forms.Form):
    display_name = forms.CharField(label=_("Name"), max_length=40, required=False)
    language = forms.ChoiceField(label=_("Language"), choices=[("fr", "Français"), ("en", "English")])
    daily_goal_xp = forms.TypedChoiceField(label=_("Daily goal"), coerce=int,
                                           choices=[(n, f"{n} XP") for n in settings.DAILY_GOAL_CHOICES])
    timezone = forms.CharField(label=_("Time zone"), max_length=64)

    def clean_timezone(self):
        tz = self.cleaned_data["timezone"].strip()
        if not valid_timezone(tz):
            raise forms.ValidationError(_("Unknown time zone."))
        return tz


class ChessComForm(forms.Form):
    username = forms.CharField(label=_("Chess.com username"), max_length=50)
