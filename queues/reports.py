"""Read-only queries behind the history and wait-time screen.

Kept apart from `services.py`, which only writes. Nothing here changes a row,
so a slow report can never hold a lock on the queue people are standing in.

Every figure comes from the cached `wait_seconds` and `service_seconds` that
the counter operations stamp on an entry as it moves, so a day's numbers do
not walk the event trail.
"""
from datetime import timedelta

from django.db.models import Avg, Count, Max, Q
from django.utils import timezone

from queues.models import Counter, EntryStatus, QueueEntry, QueueEvent, Service

CLOSED_STATUSES = [EntryStatus.SERVED, EntryStatus.SKIPPED, EntryStatus.CANCELLED]


def _minutes(seconds):
    """Seconds to whole minutes, for a figure someone reads at a glance."""
    if seconds is None:
        return None
    return int(round(seconds / 60))


def entries_on(day):
    return QueueEntry.objects.filter(token__issue_date=day)


def day_summary(day):
    """The headline row: what the day looked like from the waiting room."""
    entries = entries_on(day)
    figures = entries.aggregate(
        issued=Count("pk"),
        served=Count("pk", filter=Q(status=EntryStatus.SERVED)),
        skipped=Count("pk", filter=Q(status=EntryStatus.SKIPPED)),
        cancelled=Count("pk", filter=Q(status=EntryStatus.CANCELLED)),
        waiting=Count("pk", filter=Q(status=EntryStatus.WAITING)),
        avg_wait=Avg("wait_seconds"),
        longest_wait=Max("wait_seconds"),
        avg_service=Avg("service_seconds", filter=Q(status=EntryStatus.SERVED)),
    )
    figures["avg_wait_minutes"] = _minutes(figures["avg_wait"])
    figures["longest_wait_minutes"] = _minutes(figures["longest_wait"])
    figures["avg_service_minutes"] = _minutes(figures["avg_service"])
    figures["day"] = day
    return figures


def service_breakdown(day):
    """Per service: how many came, how long they waited, how long it took."""
    rows = (
        Service.objects.filter(tokens__issue_date=day)
        .annotate(
            issued=Count("tokens__entry", distinct=True),
            served=Count(
                "tokens__entry",
                filter=Q(tokens__entry__status=EntryStatus.SERVED),
                distinct=True,
            ),
            avg_wait=Avg("tokens__entry__wait_seconds"),
            avg_service=Avg(
                "tokens__entry__service_seconds",
                filter=Q(tokens__entry__status=EntryStatus.SERVED),
            ),
        )
        .order_by("code")
    )
    for row in rows:
        row.avg_wait_minutes = _minutes(row.avg_wait)
        row.avg_service_minutes = _minutes(row.avg_service)
    return list(rows)


def counter_breakdown(day):
    """Per counter: throughput and how long each person spent at the desk."""
    rows = (
        Counter.objects.filter(entries__token__issue_date=day)
        .annotate(
            served=Count("entries", filter=Q(entries__status=EntryStatus.SERVED)),
            skipped=Count("entries", filter=Q(entries__status=EntryStatus.SKIPPED)),
            avg_service=Avg(
                "entries__service_seconds", filter=Q(entries__status=EntryStatus.SERVED)
            ),
        )
        .select_related("assigned_staff")
        .order_by("code")
    )
    for row in rows:
        row.avg_service_minutes = _minutes(row.avg_service)
    return list(rows)


def busiest_hours(day, top=4):
    """When the room filled up, by the hour a token was taken."""
    counts = {}
    for queued_at in entries_on(day).values_list("queued_at", flat=True):
        hour = timezone.localtime(queued_at).hour
        counts[hour] = counts.get(hour, 0) + 1
    if not counts:
        return []
    busiest = max(counts.values())
    rows = [
        {"hour": hour, "count": count, "share": int(round(count * 100 / busiest))}
        for hour, count in sorted(counts.items())
    ]
    rows.sort(key=lambda row: (-row["count"], row["hour"]))
    return rows[:top]


def daily_trend(days=7, end=None):
    """One row per day, oldest first, for the bars down the side of the page."""
    end = end or timezone.localdate()
    start = end - timedelta(days=days - 1)
    rows = {
        row["token__issue_date"]: row
        for row in QueueEntry.objects.filter(token__issue_date__range=(start, end))
        .values("token__issue_date")
        .annotate(
            issued=Count("pk"),
            served=Count("pk", filter=Q(status=EntryStatus.SERVED)),
            avg_wait=Avg("wait_seconds"),
        )
    }

    trend = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        row = rows.get(day, {})
        trend.append(
            {
                "day": day,
                "issued": row.get("issued", 0),
                "served": row.get("served", 0),
                "avg_wait_minutes": _minutes(row.get("avg_wait")),
            }
        )

    busiest = max((row["issued"] for row in trend), default=0)
    for row in trend:
        row["share"] = int(round(row["issued"] * 100 / busiest)) if busiest else 0
    return trend


def recent_events(day, limit=25):
    """The trail for one day, newest first."""
    return (
        QueueEvent.objects.filter(entry__token__issue_date=day)
        .select_related("entry__token__service", "counter", "actor")
        .order_by("-at")[:limit]
    )
