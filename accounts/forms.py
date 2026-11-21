from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

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
