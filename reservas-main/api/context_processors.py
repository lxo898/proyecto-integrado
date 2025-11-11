# api/context_processors.py
from .models import Notification

def notifications_unread(request):
    """Disponibiliza el conteo de notificaciones no leídas en todos los templates."""
    if request.user.is_authenticated:
        return {
            "unread_notifications_count": Notification.objects.filter(
                user=request.user, is_read=False
            ).count()
        }
    return {"unread_notifications_count": 0}
