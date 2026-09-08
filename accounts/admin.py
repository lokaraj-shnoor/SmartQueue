from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class QueueUserAdmin(UserAdmin):
    list_display = ["username", "display_name", "email", "role", "department", "is_active"]
    list_filter = ["role", "is_active", "is_superuser"]
    search_fields = ["username", "first_name", "last_name", "email"]
    fieldsets = UserAdmin.fieldsets + (
        ("Queue profile", {"fields": ("role", "phone", "department")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Queue profile", {"fields": ("role", "phone", "department")}),
    )
