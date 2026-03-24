"""
Google OAuth2 views: login, callback, logout.
"""
from django.shortcuts import redirect, render
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from .models import CalendarIntegration


def auth_login(request):
    if not settings.GOOGLE_CLIENT_ID:
        messages.error(request, 'Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file.')
        return redirect('/')

    from .services.google_calendar import get_auth_url
    authorization_url, state = get_auth_url(request)
    request.session['oauth_state'] = state
    return redirect(authorization_url)


def auth_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')

    if error:
        messages.error(request, f'Google auth denied: {error}')
        return redirect('/')

    if not code or state != request.session.get('oauth_state'):
        messages.error(request, 'Invalid OAuth callback. Please try again.')
        return redirect('auth_login')

    try:
        from .services.google_calendar import exchange_code
        credentials = exchange_code(code, state)

        # Store / update the integration record
        CalendarIntegration.objects.filter(is_active=True).update(is_active=False)
        expiry = None
        if credentials.expiry:
            expiry = timezone.make_aware(credentials.expiry) if credentials.expiry.tzinfo is None else credentials.expiry

        integration = CalendarIntegration.objects.create(
            calendar_id='primary',
            calendar_name='Primary Calendar',
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or '',
            token_expiry=expiry,
            is_active=True,
        )
        messages.success(request, 'Google Calendar connected! Choose a calendar below.')
    except Exception as exc:
        messages.error(request, f'OAuth exchange failed: {exc}')
        return redirect('/')

    return redirect('calendar_list')


def auth_logout(request):
    CalendarIntegration.objects.filter(is_active=True).update(is_active=False)
    messages.success(request, 'Google Calendar disconnected.')
    return redirect('/')
