"""Queue operations that change state.

Views stay thin: they check permissions and report back. Everything that
writes a token, moves an entry between statuses, or leaves a trail in
QueueEvent happens here, inside one transaction, so the ledger can never
disagree with the queue.
"""
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from queues.models import (
    Counter,
    CounterSession,
    CounterStatus,
    EntryStatus,
    EventType,
    QueueEntry,
    QueueEvent,
    Service,
    SystemSettings,
    Token,
    TokenChannel,
)


class QueueError(Exception):
    """Something about the request is not allowed right now."""


def open_entry_for(user, service=None):
    """The token this person is still waiting on, if any."""
    entries = QueueEntry.objects.filter(
        token__issued_to=user,
        token__issue_date=timezone.localdate(),
        status__in=[EntryStatus.WAITING, EntryStatus.CALLED, EntryStatus.SERVING],
    ).select_related("token__service", "counter")
    if service is not None:
        entries = entries.filter(token__service=service)
    return entries.order_by("queued_at").first()


def issued_today(service, on_date=None):
    return Token.objects.filter(
        service=service, issue_date=on_date or timezone.localdate()
    ).count()


def check_can_issue(service, user):
    """Raise QueueError with a sentence the visitor can act on, or return None."""
    if not SystemSettings.load().accepting_tokens:
        raise QueueError("New tokens are paused across the whole system right now.")
    if not service.is_active:
        raise QueueError(service.name + " is not taking tokens at the moment.")
    if service.daily_token_limit and issued_today(service) >= service.daily_token_limit:
        raise QueueError(service.name + " has handed out every token for today.")
    if open_entry_for(user, service) is not None:
        raise QueueError("You already hold a token for " + service.name + ".")


@transaction.atomic
def issue_token(service, user=None, channel=TokenChannel.WEB, guest_name="", guest_phone="", priority=0):
    """Hand out the next number for a service and put it in the queue.

    Locks the service row so two people pressing at the same moment cannot be
    given the same number.
    """
    service = Service.objects.select_for_update().get(pk=service.pk)
    if user is not None:
        check_can_issue(service, user)

    token = Token.objects.create(
        service=service,
        number=service.next_token_number(),
        issued_to=user,
        guest_name=guest_name,
        guest_phone=guest_phone,
        channel=channel,
    )
    entry = QueueEntry.objects.create(token=token, priority=priority)
    QueueEvent.objects.create(entry=entry, actor=user, event=EventType.ISSUED)
    return entry


@transaction.atomic
def cancel_entry(entry, actor=None, note=""):
    """Give up a place in line. Only an entry nobody has called can be dropped."""
    if entry.status != EntryStatus.WAITING:
        raise QueueError("That token has already been called and cannot be cancelled.")
    entry.status = EntryStatus.CANCELLED
    entry.finished_at = timezone.now()
    entry.wait_seconds = int((entry.finished_at - entry.queued_at).total_seconds())
    entry.save(update_fields=["status", "finished_at", "wait_seconds"])
    QueueEvent.objects.create(
        entry=entry, counter=entry.counter, actor=actor, event=EventType.CANCELLED, note=note
    )
    return entry


def people_ahead(entry):
    """How many are in front, using the same order the callers pull from."""
    if entry.status != EntryStatus.WAITING:
        return 0
    sorts_first = Q(priority__gt=entry.priority) | Q(
        priority=entry.priority, queued_at__lt=entry.queued_at
    )
    return (
        QueueEntry.objects.filter(
            token__service=entry.token.service,
            token__issue_date=entry.token.issue_date,
            status=EntryStatus.WAITING,
        )
        .filter(sorts_first)
        .count()
    )


def estimated_minutes(entry, ahead=None):
    """Rough wait: people in front times the service average, split by counters.

    Deliberately coarse. It is a number someone glances at, not a promise.
    """
    if entry.status in {EntryStatus.CALLED, EntryStatus.SERVING}:
        return 0
    ahead = people_ahead(entry) if ahead is None else ahead
    service = entry.token.service
    desks = max(service.counters.filter(is_active=True).count(), 1)
    return int(round(ahead * service.avg_service_minutes / desks))


# --- The counter side: calling people forward ------------------------------


def waiting_for_counter(counter, limit=None):
    """The line this counter pulls from, in the order it will be called."""
    entries = (
        QueueEntry.objects.filter(
            status=EntryStatus.WAITING,
            token__issue_date=timezone.localdate(),
            token__service__in=counter.services.all(),
        )
        .select_related("token__service", "token__issued_to")
        .order_by("-priority", "queued_at")
    )
    return entries[:limit] if limit else entries


def is_stale(entry):
    """A token left on a counter from an earlier day. Nobody is standing there."""
    return entry is not None and entry.token.issue_date != timezone.localdate()


def live_serving(counter):
    """What this counter is actually serving now, ignoring yesterday's leftovers."""
    entry = counter.now_serving
    if entry is None or is_stale(entry) or not entry.is_open:
        return None
    return entry


def _require_open(counter):
    if counter.status != CounterStatus.OPEN:
        raise QueueError("Open " + counter.code + " before calling anyone forward.")


@transaction.atomic
def call_next(counter, staff):
    """Take the next person in line to this counter.

    Refuses while someone is still at the desk: finishing or skipping the
    current token is what makes room for the next one.
    """
    _require_open(counter)
    current = counter.now_serving
    if current and current.is_open:
        if not is_stale(current):
            raise QueueError(
                current.token.code + " is still at your counter. Finish or skip it first."
            )
        # A number left on the desk overnight: nobody is standing there, so
        # close it off rather than blocking today's queue behind it.
        skip_entry(current, staff, note="Left on the counter from an earlier day")
        counter.refresh_from_db()

    entry = (
        QueueEntry.objects.select_for_update(skip_locked=True)
        .filter(
            status=EntryStatus.WAITING,
            token__issue_date=timezone.localdate(),
            token__service__in=counter.services.all(),
        )
        .order_by("-priority", "queued_at")
        .first()
    )
    if entry is None:
        raise QueueError("Nobody is waiting for the services " + counter.code + " handles.")

    now = timezone.now()
    entry.status = EntryStatus.CALLED
    entry.counter = counter
    entry.called_at = now
    entry.wait_seconds = int((now - entry.queued_at).total_seconds())
    entry.save(update_fields=["status", "counter", "called_at", "wait_seconds"])

    counter.now_serving = entry
    counter.save(update_fields=["now_serving", "updated_at"])

    QueueEvent.objects.create(entry=entry, counter=counter, actor=staff, event=EventType.CALLED)
    return entry


@transaction.atomic
def recall(entry, staff):
    """Call the same number again for someone who has not walked up yet."""
    if entry.status != EntryStatus.CALLED:
        raise QueueError("Only a token that has been called can be called again.")
    entry.called_at = timezone.now()
    entry.save(update_fields=["called_at"])
    QueueEvent.objects.create(
        entry=entry, counter=entry.counter, actor=staff, event=EventType.RECALLED
    )
    return entry


@transaction.atomic
def start_serving(entry, staff):
    """The person has arrived. Starts the clock that measures service time."""
    if entry.status != EntryStatus.CALLED:
        raise QueueError("Call " + entry.token.code + " before starting to serve it.")
    entry.status = EntryStatus.SERVING
    entry.started_at = timezone.now()
    entry.served_by = staff
    entry.save(update_fields=["status", "started_at", "served_by"])
    QueueEvent.objects.create(
        entry=entry, counter=entry.counter, actor=staff, event=EventType.STARTED
    )
    return entry


@transaction.atomic
def finish_serving(entry, staff, note=""):
    """Done. Records service time and frees the counter for the next call."""
    if entry.status not in {EntryStatus.CALLED, EntryStatus.SERVING}:
        raise QueueError("That token is not at a counter.")
    now = timezone.now()
    started = entry.started_at or entry.called_at or now
    entry.status = EntryStatus.SERVED
    entry.finished_at = now
    entry.served_by = entry.served_by or staff
    entry.service_seconds = int((now - started).total_seconds())
    if note:
        entry.note = note
    entry.save(update_fields=["status", "finished_at", "served_by", "service_seconds", "note"])
    _release(entry, staff, EventType.SERVED, note, served=True)
    return entry


@transaction.atomic
def skip_entry(entry, staff, note=""):
    """Nobody came forward. Marks it skipped and frees the counter."""
    if entry.status not in {EntryStatus.CALLED, EntryStatus.SERVING}:
        raise QueueError("Only a token at a counter can be skipped.")
    entry.status = EntryStatus.SKIPPED
    entry.finished_at = timezone.now()
    if note:
        entry.note = note
    entry.save(update_fields=["status", "finished_at", "note"])
    _release(entry, staff, EventType.SKIPPED, note, served=False)
    return entry


@transaction.atomic
def requeue(entry, staff):
    """Put a skipped number back in line, ahead of its peers, and call it again."""
    if entry.status != EntryStatus.SKIPPED:
        raise QueueError("Only a skipped token can go back in line.")
    entry.status = EntryStatus.WAITING
    entry.counter = None
    entry.called_at = None
    entry.finished_at = None
    entry.priority = entry.priority + 1
    entry.save(update_fields=["status", "counter", "called_at", "finished_at", "priority"])
    QueueEvent.objects.create(
        entry=entry, actor=staff, event=EventType.ISSUED, note="Back in line after a skip"
    )
    return entry


def _release(entry, staff, event, note, served):
    """Clear the counter's display and record the closing event."""
    counter = entry.counter
    QueueEvent.objects.create(entry=entry, counter=counter, actor=staff, event=event, note=note)
    if counter is None:
        return
    if counter.now_serving_id == entry.pk:
        counter.now_serving = None
        counter.save(update_fields=["now_serving", "updated_at"])
    if served:
        # The shift row is opened lazily: an administrator may have opened the
        # desk, so the first token this person finishes is what starts it.
        session = open_shift(counter, staff)
        session.tokens_served = session.tokens_served + 1
        session.save(update_fields=["tokens_served"])


def open_shift(counter, staff):
    """This person's live shift at this counter, started if it is not running."""
    session, _ = CounterSession.objects.get_or_create(
        counter=counter, staff=staff, closed_at=None
    )
    return session


@transaction.atomic
def set_counter_status(counter, status, staff):
    """Staff open, pause and close their own desk. Opening starts a shift."""
    if status not in CounterStatus.values:
        raise QueueError("That is not a counter status.")
    was_open = counter.status == CounterStatus.OPEN
    counter.status = status
    counter.save(update_fields=["status", "updated_at"])

    if status == CounterStatus.OPEN and not was_open:
        open_shift(counter, staff)
    elif status == CounterStatus.CLOSED:
        counter.sessions.filter(staff=staff, closed_at__isnull=True).update(closed_at=timezone.now())
    return counter


# --- The wall board --------------------------------------------------------


def board_counters():
    """Every counter worth showing on the wall, in board order.

    A leftover from an earlier day is dropped from the display: the board
    only ever shows a number somebody could still walk up to.
    """
    counters = list(
        Counter.objects.filter(is_active=True)
        .exclude(status=CounterStatus.CLOSED)
        .select_related("now_serving__token__service")
        .prefetch_related("services")
        .order_by("code")
    )
    for counter in counters:
        counter.serving_now = live_serving(counter)
    return counters


def recently_called(limit=6):
    """The last numbers called, newest first, so a late arrival can catch up."""
    return (
        QueueEntry.objects.filter(
            token__issue_date=timezone.localdate(), called_at__isnull=False
        )
        .exclude(status=EntryStatus.CANCELLED)
        .select_related("token__service", "counter")
        .order_by("-called_at")[:limit]
    )


def board_service_lines():
    """Per-service waiting counts, for the strip under the counters."""
    return (
        Service.objects.filter(is_active=True)
        .annotate(
            waiting=Count(
                "tokens__entry",
                filter=Q(
                    tokens__entry__status=EntryStatus.WAITING,
                    tokens__issue_date=timezone.localdate(),
                ),
                distinct=True,
            )
        )
        .order_by("code")
    )
