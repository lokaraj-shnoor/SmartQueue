from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from accounts import oauth
from accounts.forms import LoginForm, NewPasswordForm, PasswordResetRequestForm, SignUpForm
from accounts.models import Role, User


class QueueLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["google_enabled"] = oauth.is_configured()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Signed in as " + self.request.user.display_name + ".")
        return response


class QueueLogoutView(LogoutView):
    next_page = reverse_lazy("core:landing")


class SignUpView(CreateView):
    template_name = "accounts/signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("dashboard:home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["google_enabled"] = oauth.is_configured()
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Account created. You can take tokens now.")
        return redirect(self.success_url)


# --- Forgotten passwords ---------------------------------------------------
# Django's own views do the token work. These only carry the project's
# templates and the copy people actually read.


class QueuePasswordResetView(PasswordResetView):
    """Ask for the address and send the link.

    Django answers identically whether or not the address is on file, so this
    page cannot be used to find out who holds an account here.
    """

    template_name = "accounts/password_reset.html"
    form_class = PasswordResetRequestForm
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class QueuePasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class QueuePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = NewPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class QueuePasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


# --- Sign in with Google ---------------------------------------------------


def google_start(request):
    """Send someone to Google, remembering where they were headed."""
    if not oauth.is_configured():
        messages.error(request, "Sign in with Google is not set up on this site.")
        return redirect("accounts:login")
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    next_url = request.GET.get("next", "")
    return redirect(oauth.begin(request, next_url=next_url))


def google_callback(request):
    """Google sends people back here. Match on the verified email, or sign up."""
    if not oauth.is_configured():
        messages.error(request, "Sign in with Google is not set up on this site.")
        return redirect("accounts:login")

    try:
        profile = oauth.finish(request)
    except oauth.GoogleAuthError as problem:
        messages.error(request, str(problem))
        return redirect("accounts:login")

    user, created = _user_for_google(profile)
    if not user.is_active:
        messages.error(request, "That account has been deactivated. Ask an administrator.")
        return redirect("accounts:login")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    if created:
        messages.success(request, "Account created from your Google email. You can take tokens now.")
    else:
        messages.success(request, "Signed in as " + user.display_name + ".")

    target = profile.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return redirect(target)
    return redirect("dashboard:home")


def _user_for_google(profile):
    """The account behind a verified Google email, created if it is new.

    Matching is on the email alone: staff and administrator accounts are made
    by an administrator, and this lets those people use the Google button
    without losing the role they were granted.
    """
    email = profile["email"]
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        return user, False

    user = User(
        username=_free_username(email),
        email=email,
        first_name=profile.get("name", "")[:150],
        role=Role.VISITOR,
    )
    # No password is set: this account signs in through Google, and can start
    # using a password by going through the forgotten-password flow.
    user.set_unusable_password()
    user.save()
    return user, True


def _free_username(email):
    base = "".join(ch for ch in email.split("@")[0] if ch.isalnum() or ch in "._-")[:140]
    base = base or "visitor"
    candidate = base
    suffix = 2
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = base + str(suffix)
        suffix += 1
    return candidate
