from django.contrib import admin
from .models import ExpiringProduct
from .models import DamageProduct

@admin.register(ExpiringProduct)
class ExpiringProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_name", "product_code", "initial_unit_price", "resale_price",
        "quantity", "loss_value", "staff_name", "created_date", 'reference'
    )
    search_fields = ("product_name", "product_code", "reference")
    readonly_fields = ("product_code", "initial_unit_price",
                       "loss_value", "staff", 'last_updated_by',"created_date", "description")

    def save_model(self, request, obj, form, change):
        if not change:  # New record
            obj.staff = request.user
            obj.staff_name = request.user.get_full_name() or request.user.username
        else:  # Editing record
            obj.last_updated_by = request.user
            obj.last_updated_name = request.user.get_full_name() or request.user.username
        super().save_model(request, obj, form, change)


@admin.register(DamageProduct)
class DamageProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_name", "product_code", "initial_unit_price", "resale_price",
        "quantity", "loss_value", "staff_name", "created_date", 'reference'
    )
    search_fields = ("product_name", "product_code", "reference")

    readonly_fields = (
        "product_code", "initial_unit_price",
        "loss_value", "staff", "created_date", "description", 'last_updated_by'
    )

    def save_model(self, request, obj, form, change):
        if not change:  # New record
            obj.staff = request.user
            obj.staff_name = request.user.get_full_name() or request.user.username
        else:  # Editing record
            obj.last_updated_by = request.user
            obj.last_updated_name = request.user.get_full_name() or request.user.username
        super().save_model(request, obj, form, change)
