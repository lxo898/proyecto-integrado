from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings


class Space(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True)
    capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Resource(models.Model):
    name = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField(default=1)
    space = models.ForeignKey(Space, on_delete=models.SET_NULL, null=True, blank=True, related_name="resources")

    def __str__(self):
        return self.name


class Reservation(models.Model):
    PENDING = "PEND"
    APPROVED = "APPR"
    REJECTED = "REJ"
    CANCELED = "CANC"
    STATUS_CHOICES = [
        (PENDING, "Pendiente"),
        (APPROVED, "Aprobada"),
        (REJECTED, "Rechazada"),
        (CANCELED, "Cancelada"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reservations")
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="reservations")
    start = models.DateTimeField()
    end = models.DateTimeField()
    purpose = models.CharField(max_length=250, blank=True)
    status = models.CharField(max_length=4, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    # === NUEVO/ARREGLADO: Motivo de cancelación opcional ===
    # Usa default="" (o si prefieres null, usa null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(end__gt=models.F("start")), name="reservation_end_after_start")
        ]

    def __str__(self):
        return f"{self.space} · {self.start:%Y-%m-%d %H:%M}"

    def overlaps(self):
        """Conflictos en el mismo espacio (no canceladas ni rechazadas)."""
        return Reservation.objects.exclude(pk=self.pk).filter(
            space=self.space, status__in=[self.PENDING, self.APPROVED],
            start__lt=self.end, end__gt=self.start
        )

    # --- Reglas para cancelar por el usuario ---
    def can_cancel(self, now=None) -> bool:
        """
        Permite cancelar si:
        - No está cancelada ni rechazada
        - Aún no comienza
        - Si está APROBADA, respeta ventana mínima (settings.MIN_CANCEL_WINDOW_HOURS)
        - Si está PENDIENTE, basta con que no haya comenzado
        """
        now = now or timezone.now()
        if self.status in {self.REJECTED, self.CANCELED}:
            return False
        if self.start <= now:
            return False
        if self.status == self.APPROVED:
            window_h = getattr(settings, "MIN_CANCEL_WINDOW_HOURS", 2)
            return (self.start - now).total_seconds() >= window_h * 3600
        return True

    def cancel_by_user(self, reason: str = "", actor: User | None = None):
        """
        Cambia a CANCELED, guarda motivo en cancel_reason y deja una
        breve traza en purpose (opcional). Notifica a usuario y admins.
        """
        if self.status == self.CANCELED:
            return  # idempotente

        note = (reason or "").strip()
        self.cancel_reason = note
        # Traza mínima en purpose (opcional)
        if note:
            extra = f" [Cancelada por usuario]"
            self.purpose = (self.purpose + extra) if self.purpose else extra

        self.status = self.CANCELED
        self.save()

        # Notificaciones básicas
        Notification.objects.create(
            user=self.user,
            message=f"Cancelaste la reserva '{self}'."
        )
        for admin in User.objects.filter(is_staff=True):
            Notification.objects.create(
                user=admin,
                message=f"Reserva cancelada por el usuario: '{self}'."
            )


class Approval(models.Model):
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name="approval")
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="approvals")
    decision = models.CharField(max_length=4, choices=[("APPR","Aprobar"),("REJ","Rechazar")])
    notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=30, blank=True)
    receive_emails = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username
