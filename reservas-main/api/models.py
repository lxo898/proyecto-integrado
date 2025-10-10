from django.db import models
from django.contrib.auth.models import User

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

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(end__gt=models.F("start")), name="reservation_end_after_start")
        ]

    def overlaps(self):
        """Conflictos en el mismo espacio (no canceladas ni rechazadas)."""
        return Reservation.objects.exclude(pk=self.pk).filter(
            space=self.space, status__in=[self.PENDING, self.APPROVED],
            start__lt=self.end, end__gt=self.start
        )

    def __str__(self):
        return f"{self.space} · {self.start:%Y-%m-%d %H:%M}"

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
