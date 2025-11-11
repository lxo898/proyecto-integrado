# api/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from .views import (
    UserLoginView, UserLogoutView, register,
    dashboard_user, dashboard_admin,
    availability_json,
    ReservationCreateView, ReservationDetailView, my_history, cancel_reservation,
    approvals_pending, approve_or_reject,
    SpaceListView, SpaceCreateView, SpaceUpdateView, SpaceDeleteView,
    ResourceListView, ResourceCreateView, ResourceUpdateView, ResourceDeleteView,
    notifications_view, export_reservations_csv, profile_view
)

urlpatterns = [
    # Auth
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("register/", register, name="register"),

    # --- Password reset (usa tus plantillas en /templates/auth/) ---
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/password_reset_form.html",
            email_template_name="auth/password_reset_email.html",
            subject_template_name="auth/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="auth/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="auth/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # Dashboards
    path("", dashboard_user, name="dashboard_user"),
    path("admin-dashboard/", dashboard_admin, name="dashboard_admin"),

    # Calendario / disponibilidad
    path("availability/", availability_json, name="availability_json"),

    # Reservas
    path("reservas/nueva/", ReservationCreateView.as_view(), name="reservation_new"),
    path("reservas/<int:pk>/", ReservationDetailView.as_view(), name="reservation_detail"),
    path("reservas/<int:pk>/cancelar/", cancel_reservation, name="reservation_cancel"),
    path("historial/", my_history, name="history"),

    # Aprobaciones
    path("aprobaciones/", approvals_pending, name="approvals_pending"),
    path("aprobaciones/<int:pk>/decidir/", approve_or_reject, name="approve_or_reject"),

    # Espacios
    path("espacios/", SpaceListView.as_view(), name="spaces_list"),
    path("espacios/nuevo/", SpaceCreateView.as_view(), name="space_new"),
    path("espacios/<int:pk>/editar/", SpaceUpdateView.as_view(), name="space_edit"),
    path("espacios/<int:pk>/eliminar/", SpaceDeleteView.as_view(), name="space_delete"),

    # Recursos
    path("recursos/", ResourceListView.as_view(), name="resources_list"),
    path("recursos/nuevo/", ResourceCreateView.as_view(), name="resource_new"),
    path("recursos/<int:pk>/editar/", ResourceUpdateView.as_view(), name="resource_edit"),
    path("recursos/<int:pk>/eliminar/", ResourceDeleteView.as_view(), name="resource_delete"),

    # Notificaciones, Reportes, Configuración
    path("notificaciones/", notifications_view, name="notifications"),
    path("reportes/reservas.csv", export_reservations_csv, name="export_reservations_csv"),
    path("perfil/", profile_view, name="profile"),
]
