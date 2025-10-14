# api/admin.py
from django.contrib import admin
from .models import Space, Resource, Reservation, Approval, Notification, Profile

@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "capacity", "is_active")
    search_fields = ("name", "location")
    list_filter = ("is_active",)

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity", "space")
    search_fields = ("name",)

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("space", "user", "start", "end", "status")
    list_filter = ("status", "space")
    search_fields = ("user__username", "space__name")

admin.site.register(Approval)
admin.site.register(Notification)
admin.site.register(Profile)
