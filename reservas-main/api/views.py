# api/views.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView

from .forms import (
    UserRegistrationForm, ReservationForm, ApprovalForm, LoginForm,
    SpaceForm, ResourceForm, ProfileForm
)
from .models import Reservation, Approval, Space, Resource, Notification, Profile
import csv


# ---------- Helpers / utilidades ----------
class StaffRequiredMixin(UserPassesTestMixin):
    """Permite solo a usuarios con is_staff=True."""
    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied  # 403 si está logueado pero no es staff
        return super().handle_no_permission()


def is_staff(user):
    return user.is_staff


def _notify_user(user, message: str):
    """Crea una notificación para un usuario."""
    if user:
        Notification.objects.create(user=user, message=message)


def _notify_group(group_name: str, message: str):
    """
    Notifica a todos los usuarios de un grupo (por ej. 'aseo').
    Si el grupo no existe, no hace nada (fail-safe).
    """
    try:
        grp = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return
    users = grp.user_set.all()
    for u in users:
        Notification.objects.create(user=u, message=message)


def notify_cleaning_staff(message: str):
    """
    Notifica al equipo de aseo / preparación del espacio.
    Nombre del grupo configurable por settings.CLEANING_GROUP_NAME (default 'aseo').
    """
    group_name = getattr(settings, "CLEANING_GROUP_NAME", "aseo")
    _notify_group(group_name, message)


# ---------- Autenticación ----------
class UserLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = LoginForm  # login por correo institucional (o username como compatibilidad)


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
    # En Django 5, usar POST desde la plantilla (ya está resuelto en base.html)
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
        "my_pending": my_pending,
        "upcoming": upcoming,
        "unread": unread
    })


@user_passes_test(is_staff)
def dashboard_admin(request):
    pending = Reservation.objects.filter(status=Reservation.PENDING)
    unread = request.user.notifications.filter(is_read=False).count() if request.user.is_authenticated else 0
    return render(request, "dashboard/admin.html", {"pending": pending, "unread": unread})


# ---------- Calendario / Disponibilidad ----------
@login_required
def availability_json(request):
    """
    Devuelve reservas (APROBADAS/PENDIENTES) para un space opcional en formato FullCalendar,
    con color por estado.
    """
    qs = Reservation.objects.filter(status__in=[Reservation.PENDING, Reservation.APPROVED])
    space_id = request.GET.get("space")
    if space_id:
        qs = qs.filter(space_id=space_id)

    def event_for(r: Reservation):
        # Colores: aprobado=verde, pendiente=amarillo
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Lista de recursos existentes para que el usuario pueda solicitarlos
        ctx["resources_all"] = Resource.objects.all().order_by("name")
        return ctx

    def form_valid(self, form):
        form.instance.user = self.request.user

        # El ReservationForm construye start/end a partir de date/start_slot/end_slot en clean()
        # Aquí solo tomamos recursos auxiliares para trazabilidad en 'purpose'
        resource_ids = self.request.POST.getlist("resources")  # lista de IDs
        resources = list(
            Resource.objects.filter(id__in=resource_ids).values_list("name", flat=True)
        )
        resources_notes = (self.request.POST.get("resources_notes") or "").strip()

        # Adjunta al comentario (purpose) para dejar rastro visible en historial/CSV
        if resources or resources_notes:
            partes = []
            if resources:
                partes.append("Recursos solicitados: " + ", ".join(resources))
            if resources_notes:
                partes.append("Detalle recursos: " + resources_notes)
            extra = " | ".join(partes)
            form.instance.purpose = (form.instance.purpose + " | " + extra).strip(" |") if form.instance.purpose else extra

        messages.info(self.request, "Reserva creada y enviada a aprobación.")

        # Notificar a admins (resumen de recursos si procede)
        notif_msg = "Nueva reserva pendiente de aprobación."
        det = []
        if resources: det.append("Recursos: " + ", ".join(resources))
        if resources_notes: det.append("Notas: " + resources_notes)
        if det:
            notif_msg += " " + " ".join(det)

        for admin in Profile.objects.filter(user__is_staff=True):
            Notification.objects.create(user=admin.user, message=notif_msg)

        return super().form_valid(form)


class ReservationDetailView(DetailView):
    model = Reservation
    template_name = "reservations/detail.html"

    def get_context_data(self, **kwargs):
        """
        Incluimos aprobación (si existe) para facilitar mostrar notas/decisión al usuario.
        """
        ctx = super().get_context_data(**kwargs)
        try:
            ctx["approval"] = self.object.approval  # OneToOne, puede no existir
        except Approval.DoesNotExist:
            ctx["approval"] = None
        return ctx


@login_required
def my_history(request):
    qs = Reservation.objects.filter(user=request.user).order_by("-start")
    # La plantilla invoca r.can_cancel(); la lógica vive en el modelo.
    # También puede acceder a r.approval si existe para ver notas/decisión.
    return render(request, "reservations/history.html", {"reservations": qs})


@login_required
def cancel_reservation(request, pk):
    """
    Cancela una reserva por el dueño via POST.
    Respeta la ventana mínima definida en settings.MIN_CANCEL_WINDOW_HOURS (lógica en el modelo).
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

    if not reservation.can_cancel():
        messages.error(
            request,
            "No puedes cancelar esta reserva (ya comenzó, está dentro de la ventana mínima o su estado no lo permite)."
        )
        return redirect("history")

    reason = (request.POST.get("reason") or "").strip()[:255]
    # Realiza la cancelación (ajusta estado/bitácora/razón/notificaciones al solicitante y admins)
    reservation.cancel_by_user(reason=reason, actor=request.user)
    messages.success(request, "Reserva cancelada correctamente.")

    # Avisar a equipo de aseo que ya NO se requiere preparación
    msg = (
        f"Reserva CANCELADA · {reservation.space} · "
        f"{reservation.start:%d/%m/%Y %H:%M} - {reservation.end:%H:%M} · "
        f"Solicitante: {reservation.user.username}"
        + (f" · Motivo: {reason}" if reason else "")
    )
    notify_cleaning_staff(msg)

    return redirect("history")


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
        # Acepta decisión desde botones (APPR/REJ) o desde el form
        post_data = request.POST.copy()
        btn_decision = post_data.get("decision")
        # Normaliza por si el template enviara 'approve'/'reject'
        if btn_decision in {"approve", "reject"}:
            btn_decision = "APPR" if btn_decision == "approve" else "REJ"
            post_data["decision"] = btn_decision

        form = ApprovalForm(post_data)

        if form.is_valid():
            decision = form.cleaned_data["decision"]  # "APPR" | "REJ"
            notes = form.cleaned_data.get("notes", "")

            # ⛔ Si se va a APROBAR, verifica choque con APROBADAS existentes
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

            # Actualiza estado de la reserva y notifica
            if decision == "APPR":
                reservation.status = Reservation.APPROVED
                messages.success(request, "Reserva aprobada.")
                _notify_user(
                    reservation.user,
                    f"Tu reserva '{reservation}' fue aprobada."
                    + (f" Notas: {notes}" if notes else "")
                )

                # Avisar a equipo de aseo para preparar el espacio
                msg = (
                    f"RESERVA APROBADA · Preparar espacio · {reservation.space} · "
                    f"{reservation.start:%d/%m/%Y %H:%M} - {reservation.end:%H:%M} · "
                    f"Solicitante: {reservation.user.username}"
                    + (f" · Notas: {notes}" if notes else "")
                )
                notify_cleaning_staff(msg)

            else:
                reservation.status = Reservation.REJECTED
                messages.warning(request, "Reserva rechazada.")
                _notify_user(
                    reservation.user,
                    f"Tu reserva '{reservation}' fue rechazada."
                    + (f" Motivo: {notes}" if notes else "")
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


# ---------- Reportes (CSV con comentario y notas de aprobación) ----------
@user_passes_test(is_staff)
def export_reservations_csv(request):
    """
    Exporta reservas a CSV separando 'Recursos solicitados' y 'Detalle recursos'
    del campo purpose (si vienen embebidos con ese formato).
    ?sep=semicolon (defecto) | comma | tab
    """
    sep = (request.GET.get("sep") or "semicolon").lower()
    if sep == "comma":
        delimiter = ","
    elif sep == "tab":
        delimiter = "\t"
    else:
        delimiter = ";"  # Excel en es-CL suele abrir mejor con ';'

    filename = f"reservas_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # BOM para Excel

    # Quote todo para evitar que ; o , rompan celdas
    writer = csv.writer(response, delimiter=delimiter, quoting=csv.QUOTE_ALL)

    writer.writerow([
        "ID", "Usuario", "Espacio", "Inicio", "Fin", "Estado",
        "Motivo de solicitud", "Recursos solicitados", "Detalle recursos",
        "Notas aprobación"
    ])

    def split_purpose(purpose_raw: str):
        """
        Extrae (motivo_base, recursos_list, recursos_detalle) desde purpose.
        Si no hay marcas, devuelve todo como motivo_base.
        """
        if not purpose_raw:
            return "", "", ""
        base_parts, recursos, detalle = [], "", ""
        for part in map(lambda s: s.strip(), purpose_raw.split("|")):
            low = part.lower()
            if low.startswith("recursos solicitados:"):
                recursos = part.split(":", 1)[1].strip()
            elif low.startswith("detalle recursos:"):
                detalle = part.split(":", 1)[1].strip()
            else:
                base_parts.append(part)
        motivo_base = " | ".join(base_parts).strip(" |")
        return motivo_base, recursos, detalle

    qs = Reservation.objects.select_related("user", "space").all().order_by("start")
    for r in qs:
        motivo_base, recursos_txt, recursos_detalle = split_purpose(r.purpose or "")
        appr = Approval.objects.filter(reservation=r).order_by("-id").first()
        notas_aprob = (appr.notes or "") if appr else ""
        writer.writerow([
            r.id,
            r.user.username,
            r.space.name,
            r.start.strftime("%Y-%m-%d %H:%M"),
            r.end.strftime("%Y-%m-%d %H:%M"),
            r.get_status_display(),
            motivo_base.replace("\r", " ").replace("\n", " ").strip(),
            recursos_txt.replace("\r", " ").replace("\n", " ").strip(),
            recursos_detalle.replace("\r", " ").replace("\n", " ").strip(),
            notas_aprob.replace("\r", " ").replace("\n", " ").strip(),
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


# --- Calendario de reservas (pantalla completa) ---
from django.contrib.auth.decorators import login_required
from .models import Space

@login_required
def calendar_view(request):
    """Pantalla con calendario mensual/semanal de reservas.
    Usa availability_json para cargar eventos (opcionalmente filtrados por espacio).
    """
    spaces = Space.objects.filter(is_active=True).order_by("name")
    return render(request, "calendar/index.html", {"spaces": spaces})

