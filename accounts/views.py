from django.http import HttpResponse


def register(request):
    return HttpResponse("Register route")


def login_view(request):
    return HttpResponse("Login route")


def logout_view(request):
    return HttpResponse("Logout route")
