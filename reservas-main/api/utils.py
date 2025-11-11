# api/utils.py
from typing import Iterable
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.mail import send_mail
from .models import Notification

def users_in_group(group_name: str) -> Iterable[User]:
    try:
        g = Group.objects.get(name=group_name)
        return g.user_set.all()
    except Group.DoesNotExist:
        return []

def notify_users(users: Iterable[User], message: str, email_subject: str | None = None, email_body: str | None = None):
    # Notificación interna
    for u in users:
        Notification.objects.create(user=u, message=message)

    # Correo (opcional)
    if email_subject and email_body and getattr(settings, "SEND_EMAIL_TO_CLEANING", False):
        recipient_list = [u.email for u in users if u.email]
        if recipient_list:
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                fail_silently=True,  # evita romper el flujo si el SMTP falla
            )
