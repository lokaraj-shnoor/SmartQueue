"""Startup checks for the mail configuration.

Mail is the one part of this project whose settings are only exercised when a
real person asks for a password reset, which is the worst moment to discover a
typo. These run on every `manage.py` command and say what to change.
"""
from email.utils import parseaddr

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def check_email_settings(app_configs, **kwargs):
    problems = []
    sending_for_real = "smtp" in settings.EMAIL_BACKEND

    _, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    if "@" not in address or "." not in address.split("@")[-1]:
        # Only fatal when mail is actually being sent: with the console backend
        # a nonsense sender is untidy, not a reason to refuse to start.
        level = Error if sending_for_real else Warning
        problems.append(
            level(
                "The sender address is not a real address: "
                + repr(settings.DEFAULT_FROM_EMAIL),
                hint=(
                    "EMAIL_SENDER needs an address inside the angle brackets, on a "
                    "domain you have verified with your mail provider. "
                    'For example: EMAIL_SENDER=Smart Queue <no-reply@yourdomain.com>. '
                    "A bare display name, or a domain you do not own, is refused by "
                    "the server when the first reset email is sent."
                ),
                id="accounts.E001" if sending_for_real else "accounts.W002",
            )
        )

    if sending_for_real and not settings.EMAIL_HOST_PASSWORD:
        problems.append(
            Warning(
                "An SMTP host is set but no password is.",
                hint="Set EMAIL_HOST_PASSWORD in .env, or mail will be refused.",
                id="accounts.W001",
            )
        )

    return problems
