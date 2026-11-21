from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/settings/", views.settings_view, name="settings"),
    path("profile/chess-com/", views.chesscom_link, name="chesscom_link"),
    path("profile/chess-com/unlink/", views.chesscom_unlink, name="chesscom_unlink"),
    path("profile/delete/", views.delete_account, name="delete_account"),
    path("profile/password/", views.PasswordChangeView.as_view(), name="password_change"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
        success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
]
