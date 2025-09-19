# admin.py
from django.contrib import admin
from .models import Overhead

@admin.register(Overhead)
class OverheadAdmin(admin.ModelAdmin):
    # Fields to show in list view
    list_display = (
        "id",
        "overhead_type",
        "description",
        "duration",
        "amount",
        "created_by_name",
        "created_at",
    )

    # Make all fields read-only
    readonly_fields = [f.name for f in Overhead._meta.fields]

    # Disable add/delete/change actions
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
