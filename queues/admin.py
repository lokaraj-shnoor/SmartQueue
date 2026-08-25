from django.contrib import admin

from .models import Counter, QueueEvent, Service, Token


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Counter)
class CounterAdmin(admin.ModelAdmin):
    list_display = ("name", "service", "staff", "status")
    search_fields = ("name", "service__name", "staff__username")
    list_filter = ("status", "service")


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ("token_number", "user", "service", "counter", "status", "created_at")
    search_fields = ("token_number", "user__username", "service__name")
    list_filter = ("status", "service", "counter")
    readonly_fields = ("token_number", "created_at", "called_at", "completed_at")


@admin.register(QueueEvent)
class QueueEventAdmin(admin.ModelAdmin):
    list_display = ("token", "action", "performed_by", "timestamp")
    list_filter = ("action", "timestamp")
