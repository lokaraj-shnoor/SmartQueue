from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, staff_required
from accounts.forms import StaffAccountForm
from accounts.models import Role, User
from dashboard.forms import CounterForm, ServiceForm, SystemSettingsForm
from queues import reports, services as queue_ops
from queues.models import (
    waiting_entries,
    Counter,
    CounterStatus,
    EntryStatus,
    QueueEntry,
    QueueEvent,
    Service,
    SystemSettings,
)


@login_required
def home(request):
    """Send each person to the dashboard their role can use."""
    user = request.user
    if user.is_admin_role:
        return redirect("dashboard:admin_home")
    if user.is_staff_role:
        return redirect("dashboard:staff_home")
    return redirect("dashboard:visitor_home")


# --- Administrator ---------------------------------------------------------


def _counter_board():
    return (
        Counter.objects.select_related("assigned_staff", "now_serving__token__service")
        .prefetch_related(Prefetch("services", queryset=Service.objects.order_by("code")))
        .order_by("code")
    )


def _service_list():
    return Service.objects.annotate(
        waiting=Count(
            "tokens__entry",
            filter=Q(
                tokens__entry__status=EntryStatus.WAITING,
                tokens__issue_date=timezone.localdate(),
            ),
            distinct=True,
        ),
        counters_total=Count("counters", filter=Q(counters__is_active=True), distinct=True),
    ).order_by("code")


@admin_required
def admin_home(request):
    counters = list(_counter_board())
    services = list(_service_list())
    settings_row = SystemSettings.load()

    return render(
        request,
        "dashboard/admin_home.html",
        {
            "counters": counters,
            "services": services,
            "settings_row": settings_row,
            "settings_form": SystemSettingsForm(instance=settings_row),
            "counter_statuses": CounterStatus.choices,
            "open_count": sum(1 for c in counters if c.status == CounterStatus.OPEN),
            "paused_count": sum(1 for c in counters if c.status == CounterStatus.PAUSED),
            "closed_count": sum(1 for c in counters if c.status == CounterStatus.CLOSED),
            "waiting_total": waiting_entries().count(),
            "staff_total": User.objects.filter(role=Role.STAFF, is_active=True).count(),
        },
    )


@admin_required
def service_list(request):
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service = form.save()
        messages.success(request, "Added " + service.name + ".")
        return redirect("dashboard:service_list")
    if request.method == "POST":
        messages.error(request, "Check the highlighted fields.")

    return render(
        request,
        "dashboard/service_list.html",
        {"services": _service_list(), "form": form},
    )


@admin_required
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved " + service.name + ".")
        return redirect("dashboard:service_list")

    return render(
        request,
        "dashboard/service_form.html",
        {"form": form, "service": service},
    )


@admin_required
@require_POST
def service_toggle(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.is_active = not service.is_active
    service.save(update_fields=["is_active", "updated_at"])
    state = "accepting tokens" if service.is_active else "paused"
    messages.success(request, service.name + " is now " + state + ".")
    return redirect(request.POST.get("next") or "dashboard:service_list")


@admin_required
@require_POST
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if service.tokens.exists():
        messages.error(
            request,
            service.name + " has tokens on record. Pause it instead so history stays intact.",
        )
        return redirect("dashboard:service_list")
    name = service.name
    service.delete()
    messages.success(request, "Removed " + name + ".")
    return redirect("dashboard:service_list")


@admin_required
def counter_list(request):
    form = CounterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        counter = form.save()
        messages.success(request, "Added counter " + counter.code + ".")
        return redirect("dashboard:counter_list")
    if request.method == "POST":
        messages.error(request, "Check the highlighted fields.")

    return render(
        request,
        "dashboard/counter_list.html",
        {"counters": _counter_board(), "form": form, "counter_statuses": CounterStatus.choices},
    )


@admin_required
def counter_edit(request, pk):
    counter = get_object_or_404(Counter, pk=pk)
    form = CounterForm(request.POST or None, instance=counter)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved counter " + counter.code + ".")
        return redirect("dashboard:counter_list")

    return render(
        request,
        "dashboard/counter_form.html",
        {"form": form, "counter": counter},
    )


@admin_required
@require_POST
def counter_status(request, pk):
    counter = get_object_or_404(Counter, pk=pk)
    status = request.POST.get("status")
    if status not in CounterStatus.values:
        messages.error(request, "That is not a counter status.")
    else:
        counter.status = status
        counter.save(update_fields=["status", "updated_at"])
        messages.success(
            request, counter.code + " is now " + counter.get_status_display().lower() + "."
        )
    return _back(request, "dashboard:counter_list")


@admin_required
@require_POST
def counter_delete(request, pk):
    counter = get_object_or_404(Counter, pk=pk)
    if counter.entries.exists():
        messages.error(
            request,
            counter.code + " has served tokens. Hide it from the board instead.",
        )
        return redirect("dashboard:counter_list")
    code = counter.code
    counter.delete()
    messages.success(request, "Removed counter " + code + ".")
    return redirect("dashboard:counter_list")


@admin_required
@require_POST
def queue_settings(request):
    settings_row = SystemSettings.load()
    form = SystemSettingsForm(request.POST, instance=settings_row)
    if form.is_valid():
        row = form.save(commit=False)
        row.updated_by = request.user
        row.save()
        state = "Issuing tokens." if row.accepting_tokens else "New tokens paused."
        messages.success(request, state)
    else:
        messages.error(request, "Could not save the queue settings.")
    return _back(request, "dashboard:admin_home")


@admin_required
def team_list(request):
    form = StaffAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(
            request, "Created " + user.display_name + " as " + user.get_role_display().lower() + "."
        )
        return redirect("dashboard:team_list")
    if request.method == "POST":
        messages.error(request, "Check the highlighted fields.")

    people = User.objects.exclude(role=Role.VISITOR).order_by("role", "username")
    return render(
        request,
        "dashboard/team_list.html",
        {"people": people, "form": form},
    )


@admin_required
@require_POST
def team_toggle(request, pk):
    person = get_object_or_404(User, pk=pk)
    if person == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("dashboard:team_list")
    person.is_active = not person.is_active
    person.save(update_fields=["is_active"])
    state = "active" if person.is_active else "deactivated"
    messages.success(request, person.display_name + " is now " + state + ".")
    return redirect("dashboard:team_list")


@admin_required
def history(request):
    """Wait times and throughput for one day, with the week around it."""
    day = _day_from(request.GET.get("day"))

    return render(
        request,
        "dashboard/history.html",
        {
            "day": day,
            "is_today": day == timezone.localdate(),
            "previous_day": day - timedelta(days=1),
            "next_day": day + timedelta(days=1),
            "summary": reports.day_summary(day),
            "services": reports.service_breakdown(day),
            "counters": reports.counter_breakdown(day),
            "busiest": reports.busiest_hours(day),
            "trend": reports.daily_trend(end=day),
            "events": reports.recent_events(day),
        },
    )


def _day_from(raw):
    """Read ?day=YYYY-MM-DD, falling back to today for anything unreadable."""
    parsed = parse_date(raw) if raw else None
    return parsed or timezone.localdate()


# --- Counter staff ---------------------------------------------------------


def _staff_counters(user):
    return (
        Counter.objects.filter(assigned_staff=user, is_active=True)
        .select_related("now_serving__token__service", "now_serving__token__issued_to")
        .prefetch_related(Prefetch("services", queryset=Service.objects.order_by("code")))
        .order_by("code")
    )


def _staff_counter_or_404(request, pk):
    """A counter this person is allowed to work. Admins may work any desk."""
    counters = Counter.objects.select_related("now_serving__token__service")
    if not request.user.is_admin_role:
        counters = counters.filter(assigned_staff=request.user)
    return get_object_or_404(counters, pk=pk)


def _current_entry_or_404(request, pk):
    entry = get_object_or_404(
        QueueEntry.objects.select_related("token__service", "counter"), pk=pk
    )
    if entry.counter is None:
        return entry
    if request.user.is_admin_role or entry.counter.assigned_staff_id == request.user.id:
        return entry
    raise Http404("That token is at someone else's counter.")


@staff_required
def staff_home(request):
    """The console someone works a counter from: who is here, who is next."""
    counters = list(_staff_counters(request.user))
    active = counters[0] if counters else None
    if "counter" in request.GET:
        active = next((c for c in counters if str(c.pk) == request.GET["counter"]), active)

    waiting = list(queue_ops.waiting_for_counter(active, limit=12)) if active else []
    skipped = []
    if active:
        skipped = list(
            QueueEntry.objects.filter(
                counter=active,
                status=EntryStatus.SKIPPED,
                token__issue_date=timezone.localdate(),
            ).select_related("token__service")[:5]
        )

    return render(
        request,
        "dashboard/staff_home.html",
        {
            "counters": counters,
            "counter": active,
            "current": active.now_serving if active else None,
            "waiting": waiting,
            "waiting_total": active.waiting_count if active else 0,
            "skipped": skipped,
            "served_today": QueueEntry.objects.filter(
                counter=active, status=EntryStatus.SERVED, token__issue_date=timezone.localdate()
            ).count()
            if active
            else 0,
            "counter_statuses": CounterStatus.choices,
        },
    )


def _counter_action(request, pk, operation, done):
    """Run one call-desk operation and report back on the console."""
    counter = _staff_counter_or_404(request, pk)
    try:
        result = operation(counter)
    except queue_ops.QueueError as problem:
        messages.error(request, str(problem))
    else:
        messages.success(request, done(result))
    return _back(request, "dashboard:staff_home")


def _entry_action(request, pk, operation, done):
    entry = _current_entry_or_404(request, pk)
    try:
        result = operation(entry)
    except queue_ops.QueueError as problem:
        messages.error(request, str(problem))
    else:
        messages.success(request, done(result))
    return _back(request, "dashboard:staff_home")


@staff_required
@require_POST
def call_next(request, pk):
    return _counter_action(
        request,
        pk,
        lambda counter: queue_ops.call_next(counter, request.user),
        lambda entry: "Calling " + entry.token.code + " to " + entry.counter.code + ".",
    )


@staff_required
@require_POST
def entry_recall(request, pk):
    return _entry_action(
        request,
        pk,
        lambda entry: queue_ops.recall(entry, request.user),
        lambda entry: "Called " + entry.token.code + " again.",
    )


@staff_required
@require_POST
def entry_start(request, pk):
    return _entry_action(
        request,
        pk,
        lambda entry: queue_ops.start_serving(entry, request.user),
        lambda entry: "Serving " + entry.token.code + ".",
    )


@staff_required
@require_POST
def entry_finish(request, pk):
    note = request.POST.get("note", "").strip()
    return _entry_action(
        request,
        pk,
        lambda entry: queue_ops.finish_serving(entry, request.user, note=note),
        lambda entry: "Finished " + entry.token.code + ". Call the next person when ready.",
    )


@staff_required
@require_POST
def entry_skip(request, pk):
    note = request.POST.get("note", "").strip()
    return _entry_action(
        request,
        pk,
        lambda entry: queue_ops.skip_entry(entry, request.user, note=note),
        lambda entry: "Skipped " + entry.token.code + ".",
    )


@staff_required
@require_POST
def entry_requeue(request, pk):
    return _entry_action(
        request,
        pk,
        lambda entry: queue_ops.requeue(entry, request.user),
        lambda entry: entry.token.code + " is back in line, next in priority.",
    )


@staff_required
@require_POST
def counter_shift(request, pk):
    status = request.POST.get("status", "")
    return _counter_action(
        request,
        pk,
        lambda counter: queue_ops.set_counter_status(counter, status, request.user),
        lambda counter: counter.code + " is now " + counter.get_status_display().lower() + ".",
    )


# --- Visitor ---------------------------------------------------------------


@login_required
def visitor_home(request):
    """The page someone holds their phone up to: take a token, watch it move."""
    entry = queue_ops.open_entry_for(request.user)
    ahead = queue_ops.people_ahead(entry) if entry else 0

    services = []
    for service in _service_list().filter(is_active=True):
        try:
            queue_ops.check_can_issue(service, request.user)
            service.blocked_reason = ""
        except queue_ops.QueueError as problem:
            service.blocked_reason = str(problem)
        services.append(service)

    history = (
        QueueEntry.objects.filter(token__issued_to=request.user)
        .exclude(pk=entry.pk if entry else None)
        .select_related("token__service", "counter")
        .order_by("-queued_at")[:5]
    )

    return render(
        request,
        "dashboard/visitor_home.html",
        {
            "entry": entry,
            "ahead": ahead,
            "eta_minutes": queue_ops.estimated_minutes(entry, ahead) if entry else 0,
            "services": services,
            "history": history,
        },
    )


@login_required
def token_status(request):
    """What the visitor's page polls: their token, and whether it is up.

    Small and cheap on purpose — this is hit every few seconds by every phone
    in the waiting room, so it answers with the few fields the page redraws
    and nothing else.
    """
    entry = queue_ops.open_entry_for(request.user)
    if entry is None:
        return JsonResponse({"holding": False})

    ahead = queue_ops.people_ahead(entry)
    return JsonResponse(
        {
            "holding": True,
            "entry_id": entry.pk,
            "code": entry.token.code,
            "status": entry.status,
            "status_label": entry.get_status_display(),
            "service": entry.token.service.name,
            "counter": entry.counter.code if entry.counter else "",
            "counter_name": entry.counter.name if entry.counter else "",
            "ahead": ahead,
            "eta_minutes": queue_ops.estimated_minutes(entry, ahead),
            # The page notifies when this flips, so it is the whole point of
            # the endpoint: called or serving means go to the counter.
            "is_up": entry.status in (EntryStatus.CALLED, EntryStatus.SERVING),
        }
    )


@login_required
@require_POST
def token_take(request, pk):
    service = get_object_or_404(Service, pk=pk)
    try:
        entry = queue_ops.issue_token(service, user=request.user)
    except queue_ops.QueueError as problem:
        messages.error(request, str(problem))
    else:
        messages.success(request, "Token " + entry.token.code + " is yours. Watch for your number.")
    return redirect("dashboard:visitor_home")


@login_required
@require_POST
def token_cancel(request, pk):
    entry = get_object_or_404(QueueEntry.objects.select_related("token"), pk=pk)
    if entry.token.issued_to_id != request.user.id:
        messages.error(request, "That token is not yours.")
        return redirect("dashboard:visitor_home")
    try:
        queue_ops.cancel_entry(entry, actor=request.user)
    except queue_ops.QueueError as problem:
        messages.error(request, str(problem))
    else:
        messages.success(request, "Gave up " + entry.token.code + ". You can take a new one.")
    return redirect("dashboard:visitor_home")


@login_required
def token_detail(request, pk):
    """One token, its place in line, and everything that happened to it."""
    entry = get_object_or_404(
        QueueEntry.objects.select_related("token__service", "counter", "served_by"), pk=pk
    )
    if entry.token.issued_to_id != request.user.id and not request.user.is_admin_role:
        messages.error(request, "That token is not yours.")
        return redirect("dashboard:visitor_home")

    ahead = queue_ops.people_ahead(entry)
    return render(
        request,
        "dashboard/token_detail.html",
        {
            "entry": entry,
            "ahead": ahead,
            "eta_minutes": queue_ops.estimated_minutes(entry, ahead),
            "events": QueueEvent.objects.filter(entry=entry).select_related("counter", "actor"),
        },
    )


def _back(request, fallback):
    """Return to the page the action was fired from, when it is one of ours."""
    target = request.POST.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return HttpResponseRedirect(target)
    return HttpResponseRedirect(reverse(fallback))
