# api/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Reservation, Approval, Space, Resource, Profile


class UserRegistrationForm(UserCreationForm):
    username = forms.CharField(
        label="Usuario",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "tu_usuario"})
    )
    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "nombre@inacapmail.cl"})
    )
    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Nombre"})
    )
    last_name = forms.CharField(
        label="Apellido",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Apellido"})
    )
    password1 = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "********"}),
        help_text="Mínimo 8 caracteres, evita contraseñas comunes."
    )
    password2 = forms.CharField(
        label="Repite la contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "********"})
    )

    # Campos opcionales del perfil
    phone = forms.CharField(
        label="Teléfono",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "+56 9 1234 5678"})
    )
    receive_emails = forms.BooleanField(
        label="Quiero recibir correos de notificaciones",
        required=False,
        initial=True
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username", "email", "first_name", "last_name",
            "password1", "password2", "phone", "receive_emails"
        )


# === Resto de formularios existentes (si ya los tienes, déjalos tal cual) ===

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["space", "start", "end", "purpose"]
        widgets = {
            "start": forms.TextInput(attrs={"type": "datetime-local"}),
            "end": forms.TextInput(attrs={"type": "datetime-local"}),
            "purpose": forms.Textarea(attrs={"rows": 2, "placeholder": "Describe brevemente el motivo"}),
        }


class ApprovalForm(forms.ModelForm):
    class Meta:
        model = Approval
        fields = ["decision", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Notas para el/la solicitante (opcional)"}),
        }


class SpaceForm(forms.ModelForm):
    class Meta:
        model = Space
        fields = ["name", "location", "capacity", "is_active"]


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ["name", "quantity", "space"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["phone", "receive_emails"]
