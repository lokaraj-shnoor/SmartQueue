from django.db.utils import OperationalError, ProgrammingError

from queues.models import Counter, CounterStatus, SystemSettings


def system_settings(request):
    """Expose the site-wide switches, and whatever is on the board right now.

    Swallows database errors so the first `migrate` run does not break on a
    table that does not exist yet.
    """
    try:
        serving = (
            Counter.objects.filter(status=CounterStatus.OPEN, now_serving__isnull=False)
            .select_related("now_serving__token__service")
            .order_by("code")
            .first()
        )
        return {
            "system_settings": SystemSettings.load(),
            "serving_code": serving.now_serving.token.code if serving else "",
        }
    except (OperationalError, ProgrammingError):
        return {"system_settings": None, "serving_code": ""}
