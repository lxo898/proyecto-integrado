from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Reservation, Approval, Space, Resource, Profile

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ("space", "start", "end", "purpose")
        widgets = {
            "start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned = super().clean()
        space = cleaned.get("space")
        start = cleaned.get("start")
        end = cleaned.get("end")
        if space and start and end:
            dummy = Reservation(space=space, start=start, end=end)
            if dummy.overlaps().exists():
                raise forms.ValidationError("Existe un cruce con otra reserva para ese espacio.")
        return cleaned

class ApprovalForm(forms.ModelForm):
    class Meta:
        model = Approval
        fields = ("decision", "notes")

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
