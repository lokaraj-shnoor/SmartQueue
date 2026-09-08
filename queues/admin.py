from django.contrib import admin

from queues.models import (
    Counter,
    CounterSession,
    QueueEntry,
    QueueEvent,
    Service,
    SystemSettings,
    Token,
)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "avg_service_minutes", "daily_token_limit", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Counter)
class CounterAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "status", "assigned_staff", "is_active"]
    list_filter = ["status", "is_active"]
    search_fields = ["code", "name", "location"]
    filter_horizontal = ["services"]


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ["code", "service", "issue_date", "holder_name", "channel", "issued_at"]
    list_filter = ["service", "issue_date", "channel"]
    date_hierarchy = "issue_date"


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ["token", "status", "counter", "priority", "queued_at", "served_by"]
    list_filter = ["status", "counter"]


@admin.register(CounterSession)
class CounterSessionAdmin(admin.ModelAdmin):
    list_display = ["counter", "staff", "opened_at", "closed_at", "tokens_served"]
    list_filter = ["counter"]


@admin.register(QueueEvent)
class QueueEventAdmin(admin.ModelAdmin):
    list_display = ["entry", "event", "counter", "actor", "at"]
    list_filter = ["event"]


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ["__str__", "announcement", "updated_at"]
