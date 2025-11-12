# api/context_processors.py
from .models import Notification

def notifications(request):
    """
    Agrega a todas las plantillas:
      - notif_unread_count: cantidad de no leídas
      - notif_unread_list: últimas 3 no leídas (para toasts)
    """
    if not request.user.is_authenticated:
        return {}

    qs = Notification.objects.filter(user=request.user, is_read=False).order_by("-created_at")
    return {
        "notif_unread_count": qs.count(),
        "notif_unread_list": qs[:3],  # últimas 3 para toasts
    }

