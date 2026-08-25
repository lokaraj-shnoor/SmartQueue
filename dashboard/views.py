from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from queues.models import Counter, Service, Token
from queues.services import available_staff_counter


@login_required
def dashboard(request):
    if request.user.role == User.Role.ADMIN:
        return redirect("admin_dashboard")
    if request.user.role == User.Role.STAFF:
        return redirect("staff_dashboard")

    active_token = (
        request.user.tokens.select_related("service", "counter")
        .filter(status__in=[Token.Status.WAITING, Token.Status.SERVING])
        .order_by("created_at")
        .first()
    )
    queue_position = None
    if active_token and active_token.status == Token.Status.WAITING:
        queue_position = (
            Token.objects.filter(
                service=active_token.service,
                status=Token.Status.WAITING,
                created_at__lte=active_token.created_at,
            ).count()
        )

    return render(
        request,
        "dashboard/user.html",
        {
            "active_token": active_token,
            "queue_position": queue_position,
            "services": Service.objects.filter(is_active=True),
            "recent_tokens": request.user.tokens.select_related("service").order_by("-created_at")[:5],
        },
    )


@login_required
def staff_dashboard(request):
    if request.user.role not in [User.Role.STAFF, User.Role.ADMIN]:
        return redirect("dashboard")

    counter = available_staff_counter(request.user)
    current_token = None
    waiting_tokens = Token.objects.none()
    if counter:
        current_token = (
            Token.objects.select_related("service", "counter")
            .filter(counter=counter, status=Token.Status.SERVING)
            .order_by("-called_at")
            .first()
        )
        waiting_tokens = Token.objects.filter(service=counter.service, status=Token.Status.WAITING).order_by("created_at")[:10]

    return render(
        request,
        "dashboard/staff.html",
        {
            "counter": counter,
            "current_token": current_token,
            "waiting_tokens": waiting_tokens,
        },
    )


@login_required
def admin_dashboard(request):
    if request.user.role != User.Role.ADMIN:
        return redirect("dashboard")

    today = timezone.localdate()
    tokens_today = Token.objects.filter(created_at__date=today)
    status_counts = tokens_today.values("status").annotate(total=Count("id")).order_by("status")

    return render(
        request,
        "dashboard/admin.html",
        {
            "tokens_today": tokens_today.count(),
            "active_services": Service.objects.filter(is_active=True).count(),
            "open_counters": Counter.objects.filter(status=Counter.Status.OPEN).count(),
            "waiting_tokens": Token.objects.filter(status=Token.Status.WAITING).count(),
            "serving_tokens": Token.objects.filter(status=Token.Status.SERVING).count(),
            "status_counts": status_counts,
        },
    )
