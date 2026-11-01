from __future__ import annotations

from investments.services.watchlist import unread_count


def notifications(request):
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        return {"unread_notifications_count": unread_count(request.user)}
    return {"unread_notifications_count": 0}
