"""Create the first administrator from environment variables.

`manage.py createadmin`

Django's own `createsuperuser --noinput` fails when the account already
exists, which makes it awkward in a build command that runs on every deploy.
This is idempotent: it creates the account once, leaves an existing one alone,
and does nothing at all when the variables are absent. That makes it safe to
put in a deployment pipeline on a host with no interactive shell.

    DJANGO_ADMIN_USERNAME   required to do anything
    DJANGO_ADMIN_PASSWORD   required to do anything
    DJANGO_ADMIN_EMAIL      optional

Remove the password variable once the account exists and you have signed in.
"""
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    help = "Create the first administrator account from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "").strip()
        password = os.environ.get("DJANGO_ADMIN_PASSWORD", "")
        email = os.environ.get("DJANGO_ADMIN_EMAIL", "").strip().lower()

        if not username or not password:
            self.stdout.write(
                "DJANGO_ADMIN_USERNAME or DJANGO_ADMIN_PASSWORD not set - skipping."
            )
            return

        if User.objects.filter(username__iexact=username).exists():
            self.stdout.write("Administrator " + username + " already exists - leaving it alone.")
            return

        # A weak password here would be the account that owns every counter.
        try:
            validate_password(password)
        except ValidationError as problem:
            raise CommandError(
                "That administrator password is too weak:\n  "
                + "\n  ".join(problem.messages)
            )

        if email and User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                "Another account already uses " + email + ". Password resets and Google "
                "sign-in both match on the address, so it has to be unique."
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.stdout.write(
            self.style.SUCCESS("Created administrator " + user.username + ".")
        )
        self.stdout.write("Remove DJANGO_ADMIN_PASSWORD once you have signed in.")
