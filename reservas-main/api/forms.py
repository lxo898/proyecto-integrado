# api/forms.py
from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, time, timedelta

from .models import Reservation, Approval, Space, Resource, Profile

# =========================
# Utilidades
# =========================
def _parse_hhmm(hhmm: str) -> time:
    hh, mm = hhmm.split(":")
    return time(int(hh), int(mm))

def build_day_slots():
    """
    Genera la grilla de bloques del día según las constantes:
      SLOT_INTERVAL_MIN (default 30)
      SLOT_DAY_START (default 08:30)
      SLOT_DAY_END   (default 22:00)
    Devuelve una lista de textos "HH:MM".
    """
    interval = int(getattr(settings, "SLOT_INTERVAL_MIN", 30))
    day_start = getattr(settings, "SLOT_DAY_START", "08:30")
    day_end   = getattr(settings, "SLOT_DAY_END",   "22:00")

    t0 = _parse_hhmm(day_start)
    t1 = _parse_hhmm(day_end)

    dummy = datetime(2000, 1, 1, t0.hour, t0.minute)
    end_dt = datetime(2000, 1, 1, t1.hour, t1.minute)

    out = []
    cur = dummy
    step = timedelta(minutes=interval)
    while cur <= end_dt:
        out.append(cur.strftime("%H:%M"))
        cur += step
    return out

def make_aware_if_naive(dt: datetime) -> datetime:
    """Convierte un datetime naïve a aware usando la TZ actual de Django."""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


# =========================
# Login por correo
# =========================
class LoginForm(AuthenticationForm):
    """
    El campo 'username' se usa como email para el backend.
    """
    username = forms.EmailField(
        label="Correo institucional",
        widget=forms.EmailInput(attrs={
            "placeholder": "tu.correo@inacap.cl",
            "autocomplete": "email"
        })
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )


# =========================
# Registro por correo
# =========================
def _get_allowed_domains():
    raw = getattr(settings, "INSTITUTION_EMAIL_DOMAINS", ["inacap.cl", "inacapmail.cl"])
    # Permite string "a,b,c" o lista
    if isinstance(raw, str):
        return [d.strip().lower() for d in raw.split(",") if d.strip()]
    return [d.strip().lower() for d in raw]

class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(label="Nombre", required=False)
    last_name  = forms.CharField(label="Apellido", required=False)
    email      = forms.EmailField(
        label="Correo institucional",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder":"tu.correo@inacap.cl"})
    )

    class Meta:
        model = User
        # No pedimos username en el formulario; lo seteamos = email
        fields = ("first_name", "last_name", "email", "password1", "password2")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        allowed = _get_allowed_domains()
        if "@" not in email:
            raise forms.ValidationError("Ingresa un correo válido.")
        local, domain = email.split("@", 1)
        if domain.lower() not in allowed:
            raise forms.ValidationError(
                f"El dominio del correo debe ser institucional ({', '.join(allowed)})."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def save(self, commit=True):
        user: User = super().save(commit=False)
        email = self.cleaned_data["email"].lower()
        user.email = email
        # username = email para mantener unicidad lógica sin cambiar modelo
        user.username = email
        if commit:
            user.save()
        return user


# =========================
# Reservas (con bloques)
# =========================
class ReservationForm(forms.ModelForm):
    date = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"})
    )
    start_slot = forms.ChoiceField(label="Desde")
    end_slot   = forms.ChoiceField(label="Hasta")

    class Meta:
        model = Reservation
        fields = ("space", "purpose")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        slots = build_day_slots()
        choices = [(s, s) for s in slots]
        self.fields["start_slot"].choices = choices
        self.fields["end_slot"].choices = choices

        now = timezone.localtime()
        self.fields["date"].initial = now.date()

        # Sugerir el siguiente bloque disponible según hora actual
        now_hm = now.strftime("%H:%M")
        next_idx = 0
        for i, s in enumerate(slots):
            if s >= now_hm:
                next_idx = i
                break

        self.fields["start_slot"].initial = slots[next_idx] if next_idx < len(slots) else slots[-1]
        self.fields["end_slot"].initial = slots[min(next_idx + 1, len(slots)-1)]

        self.fields["space"].label = "Espacio"
        self.fields["space"].widget.attrs.update({"class": "form-select"})
        self.fields["purpose"].label = "Motivo / propósito"
        self.fields["purpose"].widget.attrs.update({"rows": 2, "placeholder": "Breve descripción"})

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get("date")
        start_slot = cleaned.get("start_slot")
        end_slot = cleaned.get("end_slot")

        if not date or not start_slot or not end_slot:
            return cleaned

        # Validación de bloques
        slots = [s for s, _ in self.fields["start_slot"].choices]
        if start_slot not in slots or end_slot not in slots:
            raise forms.ValidationError("Selecciona bloques de horario válidos.")
        if end_slot <= start_slot:
            raise forms.ValidationError("El bloque de término debe ser mayor al de inicio.")

        sh, sm = map(int, start_slot.split(":"))
        eh, em = map(int, end_slot.split(":"))

        # Construye datetimes NAÏVE y luego los vuelve AWARE (sin usar .localize)
        start_dt = datetime(date.year, date.month, date.day, sh, sm)
        end_dt   = datetime(date.year, date.month, date.day, eh, em)
        start_dt = make_aware_if_naive(start_dt)
        end_dt   = make_aware_if_naive(end_dt)

        cleaned["_start_dt"] = start_dt
        cleaned["_end_dt"] = end_dt

        if not (end_dt > start_dt):
            raise forms.ValidationError("La hora de término debe ser posterior a la de inicio.")

        # No permitir reservas en el pasado (opcional; útil)
        if start_dt < timezone.now():
            self.add_error("date", "No puedes reservar en el pasado.")
            # No detengas otras validaciones, pero marca el error

        # Conflictos
        space = cleaned.get("space")
        if space is not None:
            conflict_qs = Reservation.objects.filter(
                space=space,
                status__in=[Reservation.PENDING, Reservation.APPROVED],
                start__lt=end_dt,
                end__gt=start_dt,
            )
            if self.instance.pk:
                conflict_qs = conflict_qs.exclude(pk=self.instance.pk)
            if conflict_qs.exists():
                raise forms.ValidationError("Existe un conflicto de horario para este espacio en ese rango.")

        return cleaned

    def save(self, commit=True):
        obj: Reservation = super().save(commit=False)
        obj.start = self.cleaned_data["_start_dt"]
        obj.end   = self.cleaned_data["_end_dt"]
        if commit:
            obj.save()
        return obj


# =========================
# Aprobaciones / Otros
# =========================
class ApprovalForm(forms.ModelForm):
    decision = forms.ChoiceField(
        choices=(("APPR", "Aprobar"), ("REJ", "Rechazar")),
        label="Decisión"
    )

    class Meta:
        model = Approval
        fields = ("decision", "notes")
        widgets = {
            "notes": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Notas para el solicitante (opcional)"}
            )
        }

class SpaceForm(forms.ModelForm):
    class Meta:
        model = Space
        fields = ("name", "location", "capacity", "is_active")

class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ("name", "quantity", "space")

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("phone", "receive_emails")
