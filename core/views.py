from django.db.models import Count, Prefetch, Q
from django.shortcuts import render
from django.utils import timezone

from queues import services as queue_ops
from queues.models import Counter, CounterStatus, EntryStatus, QueueEntry, Service


def landing(request):
    """Public page. Explains the system and shows a live token display."""
    services = list(
        Service.objects.filter(is_active=True)
        .annotate(
            waiting=Count(
                "tokens__entry",
                filter=Q(tokens__entry__status=EntryStatus.WAITING),
                distinct=True,
            )
        )
        .order_by("code")
    )
    counters = list(
        Counter.objects.filter(is_active=True)
        .select_related("now_serving__token__service")
        .prefetch_related(Prefetch("services", queryset=Service.objects.order_by("code")))
        .order_by("code")
    )

    # The hero panel shows the real system: whoever is being served right now,
    # or the number the next person would be handed.
    feature_service = services[0] if services else None
    next_number = feature_service.next_token_number() if feature_service else 1
    serving_counter = next((c for c in counters if c.now_serving), None)
    waiting_total = QueueEntry.objects.filter(status=EntryStatus.WAITING).count()
    est_wait_minutes = waiting_total * (feature_service.avg_service_minutes if feature_service else 5)

    return render(
        request,
        "core/landing.html",
        {
            "services": services,
            "counters": counters,
            "feature_service": feature_service,
            "next_number": next_number,
            "serving_counter": serving_counter,
            "est_wait_minutes": est_wait_minutes,
            "open_counter_count": sum(1 for c in counters if c.status == CounterStatus.OPEN),
            "waiting_total": waiting_total,
        },
    )


def board(request):
    """The wall display. Public, unauthenticated, and refreshes on its own.

    This is the one screen nobody interacts with: it hangs above the counters
    and is read from across a room, so it carries the numbers and nothing else.
    """
    counters = list(queue_ops.board_counters())
    serving = [c for c in counters if c.serving_now]

    return render(
        request,
        "core/board.html",
        {
            "counters": counters,
            "serving_count": len(serving),
            "open_count": sum(1 for c in counters if c.status == CounterStatus.OPEN),
            "recent": queue_ops.recently_called(),
            "service_lines": queue_ops.board_service_lines(),
            # today only, so this total and the per-service lines agree
            "waiting_total": QueueEntry.objects.filter(
                status=EntryStatus.WAITING, token__issue_date=timezone.localdate()
            ).count(),
            "refresh_seconds": 15,
        },
    )
