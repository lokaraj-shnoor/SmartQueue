from django.http import HttpResponse


def dashboard(request):
    return HttpResponse("User dashboard route")


def staff_dashboard(request):
    return HttpResponse("Staff dashboard route")


def admin_dashboard(request):
    return HttpResponse("Admin dashboard route")
