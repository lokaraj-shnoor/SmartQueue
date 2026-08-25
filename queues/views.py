from django.http import HttpResponse


def take_token(request):
    return HttpResponse("Take token route")


def live_queue(request):
    return HttpResponse("Live queue route")


def queue_history(request):
    return HttpResponse("Queue history route")


def call_next(request):
    return HttpResponse("Call next token route")


def change_token_status(request, token_id, action):
    return HttpResponse(f"Token {token_id} action route: {action}")
