# api/views.py
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView

from .forms import (
    UserRegistrationForm, ReservationForm, ApprovalForm,
    SpaceForm, ResourceForm, ProfileForm
)
from .models import Reservation, Approval, Space, Resource, Notification, Profile
import csv

# ---------- Mixins / helpers ----------
class StaffRequiredMixin(UserPassesTestMixin):
    """Permite solo a usuarios con is_staff=True."""
    def test_func(self):
        return self.request.user.is_staff
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied  # 403 si está logueado pero no es staff
        return super().handle_no_permission()

def is_staff(user):  # usado por decoradores en funciones
    return user.is_staff


# ---------- Autenticación ----------
class UserLoginView(LoginView):
    template_name = "auth/login.html"

def register(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            messages.success(request, "Cuenta creada. ¡Bienvenido!")
            login(request, user)
            return redirect("dashboard_user")
    else:
        form = UserRegistrationForm()
    return render(request, "auth/register.html", {"form": form})

class UserLogoutView(LogoutView):
    # En Django 5, usar POST desde la plantilla (ya lo ajustamos en base.html)
    pass


# ---------- Dashboards ----------
@login_required
def dashboard_user(request):
    my_pending = Reservation.objects.filter(
        user=request.user, status=Reservation.PENDING
    )[:5]
    upcoming = Reservation.objects.filter(
        user=request.user, status=Reservation.APPROVED, start__gte=timezone.now()
    )[:5]
    unread = request.user.notifications.filter(is_read=False).count()
    return render(request, "dashboard/user.html", {
        "my_pending": my_pending, "upcoming": upcoming, "unread": unread
    })

@user_passes_test(is_staff)
def dashboard_admin(request):
    pending = Reservation.objects.filter(status=Reservation.PENDING)
    return render(request, "dashboard/admin.html", {"pending": pending})


# ---------- Calendario / Disponibilidad ----------
@login_required
def availability_json(request):
    """Devuelve reservas (APROBADAS/PENDIENTES) para un space opcional en formato FullCalendar, con color por estado."""
    qs = Reservation.objects.filter(status__in=[Reservation.PENDING, Reservation.APPROVED])
    space_id = request.GET.get("space")
    if space_id:
        qs = qs.filter(space_id=space_id)

    def event_for(r: Reservation):
        # colores: aprobado=verde, pendiente=amarillo
        if r.status == Reservation.APPROVED:
            bg = "#198754"  # success
            bd = "#198754"
            fc = "#ffffff"
        else:
            bg = "#ffc107"  # warning
            bd = "#ffc107"
            fc = "#212529"

        return {
            "id": r.id,
            "title": f"{r.space.name} ({r.get_status_display()})",
            "start": r.start.isoformat(),
            "end": r.end.isoformat(),
            "extendedProps": {"status": r.status},
            "backgroundColor": bg,
            "borderColor": bd,
            "textColor": fc,
        }

    events = [event_for(r) for r in qs]
    return JsonResponse(events, safe=False)


# ---------- Reservas ----------
class ReservationCreateView(LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "reservations/form.html"
    success_url = reverse_lazy("dashboard_user")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.info(self.request, "Reserva creada y enviada a aprobación.")
        # notificar a admins
        for admin in Profile.objects.filter(user__is_staff=True):
            Notification.objects.create(
                user=admin.user,
                message="Nueva reserva pendiente de aprobación."
            )
        return super().form_valid(form)

class ReservationDetailView(DetailView):
    model = Reservation
    template_name = "reservations/detail.html"

@login_required
def my_history(request):
    qs = Reservation.objects.filter(user=request.user).order_by("-start")
    return render(request, "reservations/history.html", {"reservations": qs})


# ---------- Aprobaciones ----------
@login_required
@user_passes_test(is_staff)
def approvals_pending(request):
    qs = Reservation.objects.filter(status=Reservation.PENDING)
    return render(request, "approvals/pending.html", {"reservations": qs})

@login_required
@user_passes_test(is_staff)
def approve_or_reject(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)

    if request.method == "POST":
        # Acepta decision desde botones (APPR/REJ) o desde el form
        post_data = request.POST.copy()
        btn_decision = post_data.get("decision")
        # Normaliza por si el template viejo enviara 'approve'/'reject'
        if btn_decision in {"approve", "reject"}:
            btn_decision = "APPR" if btn_decision == "approve" else "REJ"
            post_data["decision"] = btn_decision

        form = ApprovalForm(post_data)

        if form.is_valid():
            decision = form.cleaned_data["decision"]  # "APPR" | "REJ"
            notes = form.cleaned_data.get("notes", "")

            # ⛔ si se va a APROBAR, verifica choque con APROBADAS existentes
            if decision == "APPR":
                conflict = Reservation.objects.filter(
                    space=reservation.space,
                    status=Reservation.APPROVED
                ).exclude(pk=reservation.pk).filter(
                    start__lt=reservation.end,
                    end__gt=reservation.start
                ).exists()
                if conflict:
                    messages.error(request, "No se puede aprobar: ya existe otra reserva APROBADA en ese horario.")
                    return render(
                        request, "approvals/decision_form.html",
                        {"reservation": reservation, "form": form}
                    )

            Approval.objects.update_or_create(
                reservation=reservation,
                defaults={"approver": request.user, "decision": decision, "notes": notes}
            )

            # Actualiza estado de la reserva
            if decision == "APPR":
                reservation.status = Reservation.APPROVED
                messages.success(request, "Reserva aprobada.")
                Notification.objects.create(
                    user=reservation.user,
                    message=f"Tu reserva '{reservation}' fue aprobada."
                )
            else:
                reservation.status = Reservation.REJECTED
                messages.warning(request, "Reserva rechazada.")
                Notification.objects.create(
                    user=reservation.user,
                    message=f"Tu reserva '{reservation}' fue rechazada."
                )
            reservation.save()

            return redirect("approvals_pending")
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        form = ApprovalForm()

    return render(
        request, "approvals/decision_form.html",
        {"reservation": reservation, "form": form}
    )


# ---------- CRUD Espacios ----------
class SpaceListView(ListView):
    model = Space
    template_name = "spaces/list.html"

class SpaceCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = Space
    form_class = SpaceForm
    template_name = "spaces/form.html"
    success_url = reverse_lazy("spaces_list")

class SpaceUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Space
    form_class = SpaceForm
    template_name = "spaces/form.html"
    success_url = reverse_lazy("spaces_list")

class SpaceDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = Space
    template_name = "spaces/confirm_delete.html"
    success_url = reverse_lazy("spaces_list")


# ---------- CRUD Recursos ----------
class ResourceListView(ListView):
    model = Resource
    template_name = "resources/list.html"

class ResourceCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = Resource
    form_class = ResourceForm
    template_name = "resources/form.html"
    success_url = reverse_lazy("resources_list")

class ResourceUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Resource
    form_class = ResourceForm
    template_name = "resources/form.html"
    success_url = reverse_lazy("resources_list")

class ResourceDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = Resource
    template_name = "resources/confirm_delete.html"
    success_url = reverse_lazy("resources_list")


# ---------- Notificaciones ----------
@login_required
def notifications_view(request):
    qs = request.user.notifications.order_by("-created_at")
    if request.method == "POST":
        qs.update(is_read=True)
        return redirect("notifications")
    return render(request, "notifications/list.html", {"notifications": qs})


# ---------- Reportes (CSV con separador y BOM) ----------
@user_passes_test(is_staff)
def export_reservations_csv(request):
    # Permite elegir separador por querystring: ?sep=comma | tab | ;
    sep = request.GET.get("sep", ";")
    if sep == "comma":
        delimiter = ","
    elif sep == "tab":
        delimiter = "\t"
    else:
        delimiter = ";"  # por defecto, ideal para Excel con coma decimal / configuración regional ES/CL

    filename = f"reservas_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    # BOM para que Excel detecte UTF-8 y muestre bien acentos
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)

    # ⬇️ Añadimos Comentario (purpose) y Notas aprobación (Approval.notes)
    writer.writerow(["ID","Usuario","Espacio","Inicio","Fin","Estado","Comentario","Notas de la decision final"])

    for r in Reservation.objects.select_related("user","space"):
        comentario = (r.purpose or "").replace("\r", " ").replace("\n", " ").strip()

        # Busca la aprobación más reciente (si existe)
        appr = Approval.objects.filter(reservation=r).order_by('-id').first()
        notas_aprob = ((appr.notes or "") if appr else "").replace("\r", " ").replace("\n", " ").strip()

        writer.writerow([
            r.id,
            r.user.username,
            r.space.name,
            r.start.strftime("%Y-%m-%d %H:%M"),
            r.end.strftime("%Y-%m-%d %H:%M"),
            r.get_status_display(),
            comentario,
            notas_aprob,
        ])
    return response


# ---------- Configuración (perfil) ----------
@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Preferencias guardadas.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "account/profile.html", {"form": form})
