"""Send one test message and say plainly why it failed if it did.

`manage.py mailcheck you@example.com`

Mail configuration goes wrong in a handful of predictable ways — no host set,
an account password used where an app password is required, the wrong port for
the TLS mode — and the raw SMTP exceptions do not name any of them. This prints
the settings actually in force (never the password) and translates the common
failures into the thing to go and change.
"""
import smtplib

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test email to check the SMTP settings."

    def add_arguments(self, parser):
        parser.add_argument("recipient", help="Address to send the test message to.")

    def handle(self, *args, **options):
        recipient = options["recipient"]

        self.stdout.write("Backend    " + settings.EMAIL_BACKEND.rsplit(".", 2)[-2])
        self.stdout.write("Provider   " + (settings.EMAIL_PROVIDER or "(none named)"))
        self.stdout.write("Host       " + (settings.EMAIL_HOST or "(none)"))
        self.stdout.write("Port       " + str(settings.EMAIL_PORT))
        self.stdout.write(
            "Security   " + ("SSL" if settings.EMAIL_USE_SSL else "STARTTLS" if settings.EMAIL_USE_TLS else "none")
        )
        self.stdout.write("Username   " + (settings.EMAIL_HOST_USER or "(none)"))
        self.stdout.write("Password   " + ("set" if settings.EMAIL_HOST_PASSWORD else "(none)"))
        self.stdout.write("From       " + settings.DEFAULT_FROM_EMAIL)
        self.stdout.write("")

        if not settings.EMAIL_HOST:
            self.stdout.write(
                self.style.WARNING(
                    "No SMTP host, so mail is printed here instead of sent. Set "
                    "EMAIL_PROVIDER (brevo, mailjet, smtp2go, resend, sendgrid, "
                    "gmail, outlook) with EMAIL_HOST_USER and EMAIL_HOST_PASSWORD "
                    "in .env to send for real."
                )
            )

        try:
            sent = send_mail(
                subject="Smart Queue test message",
                message=(
                    "This is the Smart Queue mail check.\n\n"
                    "If you are reading this, password reset emails will reach people."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        except smtplib.SMTPAuthenticationError as problem:
            raise CommandError(
                "The mail server refused those credentials.\n"
                "  Brevo: EMAIL_HOST_USER is the login shown on the SMTP page, often a "
                "number rather than your email; the password is the SMTP key.\n"
                "  Mailjet: API key as the username, secret key as the password.\n"
                "  Resend: the username is literally 'resend'; the password is the API key.\n"
                "  Gmail: an app password is required, and 2-Step Verification with it.\n"
                "Server said: " + str(problem)
            )
        except smtplib.SMTPSenderRefused as problem:
            raise CommandError(
                "The server would not send as " + settings.DEFAULT_FROM_EMAIL + ".\n"
                "EMAIL_SENDER must be a real address that you have verified on the "
                "provider's dashboard - a display name alone is not enough, and a "
                "domain you do not own will be refused.\n"
                "  Right:  EMAIL_SENDER=Smart Queue <you@yourdomain.com>\n"
                "  Wrong:  EMAIL_SENDER=Smart Queue <smartqueue.com>\n"
                "Server said: " + str(problem)
            )
        except (smtplib.SMTPException, OSError) as problem:
            raise CommandError(
                "Could not reach the mail server.\n"
                "  Port 587 goes with EMAIL_USE_TLS, port 465 with EMAIL_USE_SSL. "
                "Setting both, or mixing them up, fails exactly like this.\n"
                "  A firewall or network that blocks outbound SMTP does too.\n"
                "Details: " + str(problem)
            )

        if not sent:
            raise CommandError("The backend reported that nothing was sent.")

        self.stdout.write(self.style.SUCCESS("Sent to " + recipient + "."))
        if not settings.EMAIL_HOST:
            self.stdout.write("(Printed above, not delivered - no SMTP host is configured.)")
