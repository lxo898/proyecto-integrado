# api/admin.py
from django.contrib import admin
from .models import (
    Space, Resource, Reservation, Approval, Notification, Profile,
    Event, EventSpace, EventServiceRequest, EventApproval,
)

# =======================
# Espacios / Recursos
# =======================
@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "capacity", "is_active")
    search_fields = ("name", "location")
    list_filter = ("is_active",)

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity", "space")
    search_fields = ("name",)
    list_filter = ("space",)

# =======================
# Reservas
# =======================
@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("space", "user", "start", "end", "status")
    list_filter = ("status", "space")
    search_fields = ("user__username", "space__name")
    date_hierarchy = "start"

admin.site.register(Approval)
admin.site.register(Notification)
admin.site.register(Profile)

# =======================
# Eventos institucionales
# =======================
class EventSpaceInline(admin.TabularInline):
    model = EventSpace
    extra = 0
    autocomplete_fields = ("space",)
    fields = ("space", "start", "end", "setup", "buffer_before_min", "buffer_after_min")
    ordering = ("start",)

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "tipo", "sede", "status", "organizer", "created_at")
    list_filter  = ("status", "tipo", "sede", "visibility")
    search_fields = ("title", "notes", "organizer__username")
    autocomplete_fields = ("organizer",)
    inlines = [EventSpaceInline]
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Información general", {
            "fields": ("title", "tipo", "sede", "expected_attendance")
        }),
        ("Visibilidad", {
            "fields": ("visibility", "requires_registration")
        }),
        ("Organización", {
            "fields": ("organizer", "status", "notes")
        }),
        ("Metadatos", {"fields": ("created_at",)}),
    )

@admin.register(EventServiceRequest)
class EventServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("event", "area", "status", "due_at", "assigned_to")
    list_filter = ("area", "status")
    search_fields = ("event__title", "detail", "assigned_to__username")
    autocomplete_fields = ("event", "assigned_to")
    date_hierarchy = "due_at"

@admin.register(EventApproval)
class EventApprovalAdmin(admin.ModelAdmin):
    list_display = ("event", "approver", "decision", "decided_at")
    list_filter = ("decision",)
    search_fields = ("event__title", "approver__username")
    autocomplete_fields = ("event", "approver")
    date_hierarchy = "decided_at"
