from django.contrib import admin
from .models import InventoryWriteOff

@admin.register(InventoryWriteOff)
class InventoryWriteOffAdmin(admin.ModelAdmin):
    list_display = ('product', 'description', 'quantity', 'reason', 'unit_price', 'loss_value', 'created_by_name', 'date')
    list_filter = ('reason', 'date')
    search_fields = ('product__name', 'description', 'created_by_name', 'reference')
    
    # Make all fields read-only
    readonly_fields = ('product', 'description', 'quantity', 'reason', 'unit_price', 'loss_value', 'created_by_name', 'date', 'reference')

    # Prevent adding new entries
    def has_add_permission(self, request):
        return False

    # Prevent deleting entries
    def has_delete_permission(self, request, obj=None):
        return False

    # Prevent editing existing entries
    def has_change_permission(self, request, obj=None):
        return False

