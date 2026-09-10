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
    DJANGO_ADMIN_ALLOW_WEAK_PASSWORD  set to 1 to accept a password Django's
                                      validators reject (demo accounts only)
    DJANGO_ADMIN_RESET_PASSWORD       set to 1 to also reset the password of an
                                      account that already exists

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

        existing = User.objects.filter(username__iexact=username).first()
        reset_existing = os.environ.get("DJANGO_ADMIN_RESET_PASSWORD", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if existing and not reset_existing:
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

        clash = User.objects.filter(email__iexact=email)
        if existing:
            clash = clash.exclude(pk=existing.pk)
        if email and clash.exists():
            raise CommandError(
                "Another account already uses " + email + ". Password resets and Google "
                "sign-in both match on the address, so it has to be unique."
            )

        if existing:
            # A shared temporary password has to be changeable on a host with
            # no shell, which means the deploy hook has to be able to set it.
            existing.set_password(password)
            existing.role = Role.ADMIN
            existing.is_staff = True
            existing.is_superuser = True
            existing.save()
            self.stdout.write(
                self.style.SUCCESS("Reset the password for " + existing.username + ".")
            )
            self.stdout.write(
                "Unset DJANGO_ADMIN_RESET_PASSWORD, or every deploy resets it again."
            )
            return

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
