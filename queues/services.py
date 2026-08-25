from django.db import transaction
from django.utils import timezone

from .models import Counter, QueueEvent, Token
from .realtime import broadcast_queue_update


def create_token(user, service):
    token = Token.objects.create(user=user, service=service)
    QueueEvent.objects.create(token=token, action=QueueEvent.Action.CREATED, performed_by=user)
    broadcast_queue_update("token_created", serialize_token(token))
    return token


@transaction.atomic
def call_next_token(staff_user, counter):
    token = (
        Token.objects.select_for_update()
        .filter(service=counter.service, status=Token.Status.WAITING)
        .order_by("created_at")
        .first()
    )
    if token is None:
        return None

    token.counter = counter
    token.status = Token.Status.SERVING
    token.called_at = timezone.now()
    token.save(update_fields=["counter", "status", "called_at"])
    QueueEvent.objects.create(token=token, action=QueueEvent.Action.CALLED, performed_by=staff_user)
    broadcast_queue_update("token_called", serialize_token(token))
    return token


def update_token_status(token, status, performed_by):
    token.status = status
    if status == Token.Status.COMPLETED:
        token.completed_at = timezone.now()
        update_fields = ["status", "completed_at"]
        action = QueueEvent.Action.COMPLETED
    elif status == Token.Status.SKIPPED:
        update_fields = ["status"]
        action = QueueEvent.Action.SKIPPED
    elif status == Token.Status.CANCELLED:
        update_fields = ["status"]
        action = QueueEvent.Action.CANCELLED
    else:
        update_fields = ["status"]
        action = status

    token.save(update_fields=update_fields)
    QueueEvent.objects.create(token=token, action=action, performed_by=performed_by)
    broadcast_queue_update(f"token_{status.lower()}", serialize_token(token))
    return token


def available_staff_counter(user):
    if user.role == "ADMIN":
        return Counter.objects.filter(status=Counter.Status.OPEN).first()
    return user.assigned_counters.filter(status=Counter.Status.OPEN).first()


def serialize_token(token):
    return {
        "id": token.id,
        "token_number": token.token_number,
        "service": token.service.name,
        "counter": token.counter.name if token.counter else None,
        "status": token.status,
    }
