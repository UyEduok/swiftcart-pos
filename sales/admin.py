from django.contrib import admin
from .models import Sale, SaleItem, Customer, Receipt


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0  # no empty extra rows
    can_delete = False  # prevent deletion
    readonly_fields = (
        "product", "quantity", "unit_price", "vat_value", "discount_value","cost_price", "profit", "amount", "sale_type"
    )

    # disable the add button completely
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "staff", "total_amount", "sale_date", 'reference')
    readonly_fields = ("reference", "total_cost", "total_vat", "total_discount", "total_amount", "total_profit", "payment_type", "staff", "staff_name", "sale_date", 
    "customer")
    list_filter = ("sale_date", "staff_name", "payment_type")
    search_fields = ("customer__name", "staff_name", 'reference')
    inlines = [SaleItemInline]


    def save_model(self, request, obj, form, change):
        if not change:
            # On create: assign creator (staff) and staff_name
            if not obj.staff:
                obj.staff = request.user
            if obj.staff and not obj.staff_name:
                obj.staff_name = obj.staff.get_full_name() or obj.staff.username

        super().save_model(request, obj, form, change)


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "sales_reference", "file", "created_at")
    readonly_fields = ("sale", "file", "sales_reference", "receipt_number", "created_at")
    search_fields = ("sales_reference", "receipt_number")
    ordering = ("-created_at",)


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "product", "quantity", "unit_price", "amount")
    readonly_fields = ("sale", "amount", "product", "quantity","cost_price", "unit_price", "discount_value", "vat_value", "profit", "sale_type")
    list_filter = ("sale_type",)
    search_fields = ("product__name",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'status', 'badge', "created_at", 'created_by', 'updated_at', 'updated_by')
    list_filter = ('status', 'badge')
    search_fields = ('name', 'phone', 'email')
    readonly_fields = ('badge', "created_at", 'created_by', 'updated_at', 'updated_by')

    def colored_badge(self, obj):
        color = {
            'Top Customer': 'gold',
            'Normal Customer': 'gray',
            'Low Customer': 'red',
        }.get(obj.badge, 'black')

        if obj.badge:
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color,
                obj.badge
            )
        return '-'

    colored_badge.short_description = 'Badge'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            # New object
            obj.created_by = request.user
        else:
            # Existing object
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)