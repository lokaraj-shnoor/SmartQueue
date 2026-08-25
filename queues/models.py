from django.conf import settings
from django.db import models
from django.utils import timezone


class Service(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Counter(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        PAUSED = "PAUSED", "Paused"

    name = models.CharField(max_length=120)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="counters")
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_counters",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["service__name", "name"]
        unique_together = ("name", "service")

    def __str__(self):
        return f"{self.name} - {self.service.name}"


class Token(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        SERVING = "SERVING", "Serving"
        COMPLETED = "COMPLETED", "Completed"
        SKIPPED = "SKIPPED", "Skipped"
        CANCELLED = "CANCELLED", "Cancelled"

    token_number = models.CharField(max_length=30, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tokens")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="tokens")
    counter = models.ForeignKey(
        Counter,
        on_delete=models.SET_NULL,
        related_name="tokens",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if not self.token_number:
            today = timezone.localdate().strftime("%Y%m%d")
            count = Token.objects.filter(created_at__date=timezone.localdate()).count() + 1
            self.token_number = f"Q{today}-{count:03d}"
        super().save(*args, **kwargs)

    @property
    def waiting_minutes(self):
        if not self.called_at:
            return None
        return int((self.called_at - self.created_at).total_seconds() // 60)

    def __str__(self):
        return self.token_number


class QueueEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        CALLED = "CALLED", "Called"
        COMPLETED = "COMPLETED", "Completed"
        SKIPPED = "SKIPPED", "Skipped"
        CANCELLED = "CANCELLED", "Cancelled"

    token = models.ForeignKey(Token, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=20, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="queue_events",
        null=True,
        blank=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.token.token_number} {self.action}"
