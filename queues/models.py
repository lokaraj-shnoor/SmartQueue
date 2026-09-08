"""Schema for the whole Smart Queue feature set.

Only a subset of these models is driven by a screen in this phase, but the
shape is final: issuing tokens, calling people forward, and reporting on wait
times all read and write these tables without further structural migrations.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class CounterStatus(models.TextChoices):
    OPEN = "open", "Open"
    PAUSED = "paused", "Paused"
    CLOSED = "closed", "Closed"


class EntryStatus(models.TextChoices):
    WAITING = "waiting", "Waiting"
    CALLED = "called", "Called"
    SERVING = "serving", "Serving"
    SERVED = "served", "Served"
    SKIPPED = "skipped", "Skipped"
    CANCELLED = "cancelled", "Cancelled"


class TokenChannel(models.TextChoices):
    WEB = "web", "Web"
    KIOSK = "kiosk", "Kiosk"
    COUNTER = "counter", "Issued at counter"


class EventType(models.TextChoices):
    ISSUED = "issued", "Token issued"
    CALLED = "called", "Called to counter"
    RECALLED = "recalled", "Called again"
    STARTED = "started", "Service started"
    SERVED = "served", "Service finished"
    SKIPPED = "skipped", "Skipped"
    CANCELLED = "cancelled", "Cancelled"
    TRANSFERRED = "transferred", "Moved to another counter"


class SystemSettings(models.Model):
    """One row. Site-wide switches an administrator can flip."""

    accepting_tokens = models.BooleanField(
        default=True,
        help_text="Turn off to stop issuing new tokens everywhere at once.",
    )
    announcement = models.CharField(
        max_length=240,
        blank=True,
        help_text="Shown on the landing page and the public board.",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = "system settings"
        verbose_name_plural = "system settings"

    def __str__(self):
        return "Accepting tokens" if self.accepting_tokens else "Token issuing paused"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Service(models.Model):
    """A thing people queue for: Fee payment, Blood test, Transcript pickup."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    code = models.CharField(
        max_length=3,
        unique=True,
        help_text="Prefix printed on the token, for example A or FEE.",
    )
    description = models.CharField(max_length=240, blank=True)
    avg_service_minutes = models.PositiveIntegerField(
        default=5, help_text="Starting estimate. Real averages replace it once served."
    )
    daily_token_limit = models.PositiveIntegerField(
        default=0, help_text="0 means no limit."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    @property
    def waiting_count(self):
        return QueueEntry.objects.filter(
            token__service=self, status=EntryStatus.WAITING
        ).count()

    @property
    def counter_count(self):
        return self.counters.filter(is_active=True).count()

    def next_token_number(self, on_date=None):
        """Next number for the day. Numbering restarts each day per service."""
        on_date = on_date or timezone.localdate()
        last = (
            Token.objects.filter(service=self, issue_date=on_date)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        return (last or 0) + 1


class Counter(models.Model):
    """A physical desk or window that serves one or more services."""

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=12, unique=True, help_text="Shown on the board, e.g. C1.")
    location = models.CharField(max_length=160, blank=True)
    services = models.ManyToManyField(Service, related_name="counters", blank=True)
    status = models.CharField(
        max_length=12, choices=CounterStatus.choices, default=CounterStatus.CLOSED
    )
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_counters",
    )
    now_serving = models.ForeignKey(
        "queues.QueueEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code + " - " + self.name

    @property
    def is_open(self):
        return self.status == CounterStatus.OPEN

    @property
    def waiting_count(self):
        return QueueEntry.objects.filter(
            token__service__in=self.services.all(), status=EntryStatus.WAITING
        ).count()


class Token(models.Model):
    """The ticket someone holds. Numbering restarts daily, per service."""

    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="tokens")
    number = models.PositiveIntegerField()
    issue_date = models.DateField(default=timezone.localdate)
    issued_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tokens",
        help_text="Empty for walk-ins issued at a counter or kiosk.",
    )
    guest_name = models.CharField(max_length=120, blank=True)
    guest_phone = models.CharField(max_length=32, blank=True)
    channel = models.CharField(
        max_length=12, choices=TokenChannel.choices, default=TokenChannel.WEB
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["service", "issue_date", "number"], name="unique_token_per_service_day"
            )
        ]
        indexes = [models.Index(fields=["issue_date", "service"])]

    def __str__(self):
        return self.code

    @property
    def code(self):
        return self.service.code + "-" + str(self.number).zfill(3)

    @property
    def holder_name(self):
        if self.issued_to:
            return self.issued_to.display_name
        return self.guest_name or "Walk-in"


class QueueEntry(models.Model):
    """A token's position and lifecycle inside the queue."""

    token = models.OneToOneField(Token, on_delete=models.CASCADE, related_name="entry")
    counter = models.ForeignKey(
        Counter, null=True, blank=True, on_delete=models.SET_NULL, related_name="entries"
    )
    status = models.CharField(
        max_length=12, choices=EntryStatus.choices, default=EntryStatus.WAITING
    )
    priority = models.IntegerField(
        default=0, help_text="Higher goes first. Use for accessibility or urgent cases."
    )
    queued_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    served_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entries_served",
    )
    # Cached so the statistics views do not recompute across the whole history.
    wait_seconds = models.PositiveIntegerField(null=True, blank=True)
    service_seconds = models.PositiveIntegerField(null=True, blank=True)
    note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-priority", "queued_at"]
        verbose_name_plural = "queue entries"
        indexes = [
            models.Index(fields=["status", "priority", "queued_at"]),
            models.Index(fields=["counter", "status"]),
        ]

    def __str__(self):
        return self.token.code + " (" + self.get_status_display() + ")"

    @property
    def is_open(self):
        return self.status in {EntryStatus.WAITING, EntryStatus.CALLED, EntryStatus.SERVING}

    @property
    def waited_seconds(self):
        """Wait so far, or the recorded wait once the person was called."""
        if self.wait_seconds is not None:
            return self.wait_seconds
        end = self.called_at or timezone.now()
        return int((end - self.queued_at).total_seconds())


class CounterSession(models.Model):
    """One staff member's shift at one counter. Feeds the statistics views."""

    counter = models.ForeignKey(Counter, on_delete=models.CASCADE, related_name="sessions")
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="counter_sessions"
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    tokens_served = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self):
        return self.counter.code + " / " + self.staff.display_name

    @property
    def is_live(self):
        return self.closed_at is None


class QueueEvent(models.Model):
    """Append-only trail. The history screen reads this, nothing else writes it."""

    entry = models.ForeignKey(QueueEntry, on_delete=models.CASCADE, related_name="events")
    counter = models.ForeignKey(
        Counter, null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    event = models.CharField(max_length=16, choices=EventType.choices)
    at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-at"]
        indexes = [models.Index(fields=["entry", "at"])]

    def __str__(self):
        return self.get_event_display() + " - " + self.entry.token.code
