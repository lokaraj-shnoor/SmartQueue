from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from .forms import QueueHistoryFilterForm, TokenCreateForm
from .models import Counter, Service, Token
from .services import available_staff_counter, call_next_token, create_token, update_token_status


def role_required(*roles):
    def decorator(view_func):
        @login_required
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, "You do not have permission to access that page.")
                return redirect("dashboard")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


@login_required
def take_token(request):
    if request.method == "POST":
        form = TokenCreateForm(request.POST)
        if form.is_valid():
            token = create_token(request.user, form.cleaned_data["service"])
            messages.success(request, f"Token {token.token_number} generated.")
            return redirect("dashboard")
    else:
        form = TokenCreateForm()

    return render(request, "queues/take_token.html", {"form": form})


@login_required
def live_queue(request):
    currently_serving = (
        Token.objects.select_related("service", "counter")
        .filter(status=Token.Status.SERVING)
        .order_by("counter__name")
    )
    waiting_tokens = (
        Token.objects.select_related("service")
        .filter(status=Token.Status.WAITING)
        .order_by("created_at")[:10]
    )
    return render(
        request,
        "queues/live_queue.html",
        {"currently_serving": currently_serving, "waiting_tokens": waiting_tokens},
    )


@role_required(User.Role.STAFF, User.Role.ADMIN)
def call_next(request):
    counter = available_staff_counter(request.user)
    if not counter:
        messages.error(request, "No open counter is assigned to you.")
        return redirect("staff_dashboard")

    token = call_next_token(request.user, counter)
    if token:
        messages.success(request, f"Calling token {token.token_number}.")
    else:
        messages.info(request, "No waiting tokens for this counter's service.")
    return redirect("staff_dashboard")


@role_required(User.Role.STAFF, User.Role.ADMIN)
def change_token_status(request, token_id, action):
    token = get_object_or_404(Token, id=token_id)
    actions = {
        "complete": Token.Status.COMPLETED,
        "skip": Token.Status.SKIPPED,
        "cancel": Token.Status.CANCELLED,
    }
    status = actions.get(action)
    if status is None:
        messages.error(request, "Unknown token action.")
        return redirect("staff_dashboard")

    update_token_status(token, status, request.user)
    messages.success(request, f"Token {token.token_number} marked as {status.lower()}.")
    return redirect("staff_dashboard")


@role_required(User.Role.STAFF, User.Role.ADMIN)
def queue_history(request):
    form = QueueHistoryFilterForm(request.GET or None)
    tokens = Token.objects.select_related("user", "service", "counter").order_by("-created_at")

    if form.is_valid():
        query = form.cleaned_data.get("query")
        status = form.cleaned_data.get("status")
        service = form.cleaned_data.get("service")
        date = form.cleaned_data.get("date")

        if query:
            tokens = tokens.filter(
                Q(token_number__icontains=query)
                | Q(user__username__icontains=query)
                | Q(user__email__icontains=query)
            )
        if status:
            tokens = tokens.filter(status=status)
        if service:
            tokens = tokens.filter(service=service)
        if date:
            tokens = tokens.filter(created_at__date=date)

    average_wait = (
        Token.objects.filter(called_at__isnull=False)
        .annotate(wait_time=ExpressionWrapper(F("called_at") - F("created_at"), output_field=DurationField()))
        .aggregate(avg=Avg("wait_time"))
        .get("avg")
    )

    return render(
        request,
        "queues/history.html",
        {
            "form": form,
            "tokens": tokens[:100],
            "average_wait": average_wait,
            "services_count": Service.objects.count(),
            "counters_count": Counter.objects.count(),
        },
    )
