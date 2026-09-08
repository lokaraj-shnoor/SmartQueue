from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    """Who someone is inside the queue system.

    ADMIN configures services and counters. STAFF works a counter and calls
    people forward. VISITOR takes tokens and watches the board.
    """

    ADMIN = "admin", "Administrator"
    STAFF = "staff", "Counter staff"
    VISITOR = "visitor", "Visitor"


class User(AbstractUser):
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.VISITOR,
        help_text="Controls which dashboard and actions this account can reach.",
    )
    phone = models.CharField(max_length=32, blank=True)
    # Staff only: the desk or office this person normally works from.
    department = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = [p for p in self.display_name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_superuser

    @property
    def is_staff_role(self):
        return self.role == Role.STAFF

    @property
    def is_visitor_role(self):
        return self.role == Role.VISITOR and not self.is_superuser

    def save(self, *args, **kwargs):
        # Django-admin access follows the queue role, so an administrator does
        # not need a second set of permissions granted by hand.
        if self.role == Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)
