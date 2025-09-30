from django.contrib import admin
from .models import ExpiringProduct, DamageProduct
from django.utils import timezone


class BaseProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_name", "product_code", "initial_unit_price", "resale_price",
        "quantity", "loss_value", "staff_name", "created_date", "reference"
    )
    search_fields = ("product_name", "product_code", "reference")

    readonly_fields = (
        "product_name", "product_code", "initial_unit_price", "quantity",
        "loss_value", "staff", "staff_name", "created_date",
        "reference", "description", "last_updated_by", "last_updated_name", "updated_date"
    )

    fields = (
        "product_name", "product_code", "description", "initial_unit_price", "resale_price",
        "quantity", "loss_value", "staff", "staff_name", "created_date", "last_updated_by",
        "last_updated_name", "updated_date", "reference",
    )

    def has_add_permission(self, request):
        # Prevent creation of new objects
        return False

    def save_model(self, request, obj, form, change):
        if change:  # Editing record
            obj.last_updated_by = request.user
            obj.last_updated_name = request.user.get_full_name() or request.user.username
            obj.updated_date = timezone.now() 
        super().save_model(request, obj, form, change)


@admin.register(ExpiringProduct)
class ExpiringProductAdmin(BaseProductAdmin):
    pass


@admin.register(DamageProduct)
class DamageProductAdmin(BaseProductAdmin):
    pass
