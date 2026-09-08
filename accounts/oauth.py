"""Sign in with Google, as an authorization code flow with PKCE.

Deliberately small and dependency-free beyond `requests`: this project needs
one provider and one claim from it — a verified email address — so a full
social-auth framework would be more moving parts than the feature has.

The ID token is read without checking its signature, which is safe only
because of where it comes from: it is fetched by this server, over TLS, in a
direct call to Google's token endpoint, using the client secret. A token that
arrives any other way must never be trusted this way. The claims that do not
depend on the signature are still checked below: audience, issuer, expiry, and
whether Google says the address is verified.
"""
import base64
import binascii
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode

import requests
from django.conf import settings

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
SCOPES = "openid email profile"

STATE_KEY = "google_oauth_state"
VERIFIER_KEY = "google_oauth_verifier"
NEXT_KEY = "google_oauth_next"


class GoogleAuthError(Exception):
    """The sign-in could not be completed. The message is shown to the user."""


def is_configured():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def redirect_uri(request):
    """Must match a redirect URI registered on the Google client, exactly."""
    return request.build_absolute_uri("/accounts/google/callback/")


def begin(request, next_url=""):
    """Start the flow: remember the state and verifier, return where to send them."""
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )

    request.session[STATE_KEY] = state
    request.session[VERIFIER_KEY] = verifier
    request.session[NEXT_KEY] = next_url

    query = urlencode(
        {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri(request),
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return AUTH_ENDPOINT + "?" + query


def finish(request):
    """Handle Google's redirect back. Returns the verified profile as a dict."""
    expected_state = request.session.pop(STATE_KEY, None)
    verifier = request.session.pop(VERIFIER_KEY, None)

    if request.GET.get("error"):
        raise GoogleAuthError("Google did not complete the sign-in.")

    state = request.GET.get("state", "")
    # secrets.compare_digest keeps the check constant-time; a missing state in
    # the session means the flow did not start here.
    if not expected_state or not state or not secrets.compare_digest(state, expected_state):
        raise GoogleAuthError("That sign-in link did not come from this browser. Try again.")

    code = request.GET.get("code", "")
    if not code:
        raise GoogleAuthError("Google did not return a sign-in code.")

    payload = _exchange(code, verifier, redirect_uri(request))
    claims = _read_id_token(payload.get("id_token", ""))

    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise GoogleAuthError("That Google account has no email address on it.")
    if claims.get("email_verified") not in (True, "true"):
        raise GoogleAuthError("Google has not verified the email on that account.")

    return {
        "email": email,
        "name": (claims.get("name") or "").strip(),
        "subject": claims.get("sub", ""),
        "next": request.session.pop(NEXT_KEY, "") or "",
    }


def _exchange(code, verifier, callback):
    try:
        response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": callback,
                "grant_type": "authorization_code",
                "code_verifier": verifier or "",
            },
            timeout=10,
        )
    except requests.RequestException:
        raise GoogleAuthError("Could not reach Google. Try again in a moment.")

    if response.status_code != 200:
        raise GoogleAuthError("Google rejected the sign-in. Try again.")
    return response.json()


def _read_id_token(token):
    """Decode the ID token's claims and check everything but the signature."""
    parts = token.split(".")
    if len(parts) != 3:
        raise GoogleAuthError("Google returned an unreadable sign-in token.")

    body = parts[1]
    padding = "=" * (-len(body) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(body + padding))
    except (ValueError, binascii.Error):
        raise GoogleAuthError("Google returned an unreadable sign-in token.")

    if claims.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID:
        raise GoogleAuthError("That sign-in was issued for a different application.")
    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("That sign-in did not come from Google.")
    if int(claims.get("exp", 0)) <= int(time.time()):
        raise GoogleAuthError("That sign-in has expired. Try again.")
    return claims
