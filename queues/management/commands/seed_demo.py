from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from queues.models import Counter, Service


class Command(BaseCommand):
    help = "Create demo users, services, and counters for local development."

    def handle(self, *args, **options):
        User = get_user_model()

        admin, _ = User.objects.update_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password("Admin@123")
        admin.save()

        staff, _ = User.objects.update_or_create(
            username="staff",
            defaults={
                "email": "staff@example.com",
                "role": User.Role.STAFF,
                "is_staff": True,
            },
        )
        staff.set_password("Staff@123")
        staff.save()

        user, _ = User.objects.update_or_create(
            username="user",
            defaults={
                "email": "user@example.com",
                "role": User.Role.USER,
            },
        )
        user.set_password("User@123")
        user.save()

        admissions, _ = Service.objects.update_or_create(
            name="Admissions Office",
            defaults={"description": "Applications, forms, and admission help.", "is_active": True},
        )
        clinic, _ = Service.objects.update_or_create(
            name="Campus Clinic",
            defaults={"description": "Student health consultations.", "is_active": True},
        )
        lab, _ = Service.objects.update_or_create(
            name="Computer Lab Help Desk",
            defaults={"description": "Lab access and technical support.", "is_active": True},
        )

        Counter.objects.update_or_create(
            name="Counter 1",
            service=admissions,
            defaults={"staff": staff, "status": Counter.Status.OPEN},
        )
        Counter.objects.update_or_create(
            name="Clinic Desk",
            service=clinic,
            defaults={"staff": staff, "status": Counter.Status.OPEN},
        )
        Counter.objects.update_or_create(
            name="Lab Support",
            service=lab,
            defaults={"staff": staff, "status": Counter.Status.PAUSED},
        )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write("Admin: admin / Admin@123")
        self.stdout.write("Staff: staff / Staff@123")
        self.stdout.write("User: user / User@123")
