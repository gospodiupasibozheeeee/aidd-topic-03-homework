from dashboard.models import PriceNotification


def notifications_processor(request):
    """Добавляет количество непрочитанных уведомлений в контекст шаблонов."""
    if request.user.is_authenticated:
        try:
            count = PriceNotification.objects.filter(
                user=request.user, is_read=False
            ).count()
            return {"unread_notifications_count": count}
        except Exception:
            return {"unread_notifications_count": 0}
    return {"unread_notifications_count": 0}
