from django.contrib import admin
from .models import StockHistory, ProductBatch, SupplierProductSupply, SupplierProductSupply
from django.utils.html import format_html
from .models import Product, Category, Supplier, Unit
from django.utils import timezone
today = timezone.now().date()

# Change the text in the top-left corner of admin
admin.site.site_header = "SwiftCart Administration"

# Change the browser tab title
admin.site.site_title = "SwiftCart Admin Portal"

# Change the dashboard heading
admin.site.index_title = "Welcome to SwiftCart Admin"

# Set the URL that the "View Site" button points to
admin.site.site_url = "http://localhost:5173/inventory-dashboard"



class SupplierProductSupplyInline(admin.TabularInline):
    model = SupplierProductSupply
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [SupplierProductSupplyInline]
    list_display = (
        "product_code", "name", "unit_price", "discount", "discount_quantity", "quantity", "min_stock_threshold", 
        "vat_value", "created_at"
    )
    list_filter = ("category","apply_vat", "expiry_date")
    search_fields = ("product_code", "name", "description")
    ordering = ("-created_at",)
    list_editable = ("unit_price", "min_stock_threshold", "vat_value", "discount", "discount_quantity", "min_stock_threshold",)

    readonly_fields = (
        "created_at",
        'created_by_name',
        'updated_by_name',
        'updated_at',
        "product_image_preview",
        "quantity",
        "product_code",
    )

    fieldsets = (
        ("Basic Info", {
            "fields": ("product_code", "name",  "description", 'status')
        }),
        ("Pricing", {
            "fields": (
                "unit_buying_price", "markup_percentage", "unit_price",
                "discount_quantity", "discount_percentage", "discount",
            )
        }),
        ("Stock", {
            "fields": ("quantity", "min_stock_threshold")
        }),
        ("Expiry", {
            "fields": ("expiry_date", "expiry_min_threshold_days")
        }),
        ("Relations", {
            "fields": ("category", "unit", "measurement_unit", "measurement_value")
        }),
        ("VAT", {
            "fields": ("apply_vat", "vat_value")
        }),
        ("Image", {
            "fields": ("product_image", "product_image_preview")
        }),
        ("Meta", {
             "fields": ("created_at", "updated_at", "created_by_name", "updated_by_name")
        }),
    )

    def product_image_preview(self, obj):
        if obj.product_image:
            return f'<img src="{obj.product_image.url}" width="80" height="80" style="object-fit: cover;" />'
        return "No image"
    product_image_preview.allow_tags = True
    product_image_preview.short_description = "Image Preview"

    def save_model(self, request, obj, form, change):
        if not change:
            # On create
            if not obj.created_by:
                obj.created_by = request.user
        else:
            # On update
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Unit)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = ("product",  "batch_number", "quantity_left", "expiry_date", "expiry_status", "created_at", "created_by",)
    list_filter = ("expiry_date", "product")
    search_fields = ("batch_number", "product__name", "product__product_code")
    ordering = ("expiry_date",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    def expiry_status(self, obj):
        """Show a color-coded expiry status."""
        if obj.quantity_left == 0:
            return format_html('<span style="color:green;">Sold out</span>')
        if not obj.expiry_date:
            return format_html('<span style="color:gray;">No expiry</span>')

        today = timezone.now().date()
        threshold_days = obj.expiry_min_threshold_days or 0

        if obj.expiry_date < today:
            return format_html('<span style="color:red; font-weight:bold;">Expired</span>')
        elif (obj.expiry_date - today).days <= threshold_days:
            return format_html('<span style="color:orange; font-weight:bold;">Near Expiry</span>')
        return format_html('<span style="color:green;">Good</span>')



    def save_model(self, request, obj, form, change):
        """Automatically set created_by and updated_by."""
        if not obj.pk:  # New batch
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)



@admin.register(StockHistory)
class StockHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'action', 'quantity', 'action_by', 'date')
    readonly_fields = ('product', 'action', 'quantity', 'action_by', 'date', 'notes')
    list_filter = ('action', 'action_by', 'date',)
    search_fields = ('product__name', 'product__product_code',)
    
    # Disable add, delete, and change
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "colored_badge")
    search_fields = ("name", "phone", "email", "bank_name", "account_number")
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')

    def colored_badge(self, obj):
        if obj.badge == "Top Supplier":
            color = "gold"
        elif obj.badge == "Low Supplier":
            color = "red"
        else:
            return ""  # No badge for normal suppliers

        return format_html(
            '<span style="background-color: {}; color: black; '
            'padding: 3px 8px; border-radius: 5px; font-weight: bold;">{}</span>',
            color,
            obj.badge
        )
    colored_badge.short_description = "Badge"
    colored_badge.admin_order_field = "badge"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(SupplierProductSupply)
class SupplierProductSupplyAdmin(admin.ModelAdmin):
    list_display = ("supplier", "product", "quantity_supplied", "unit_price", "total_amount", "supply_date")
    list_filter = ("supplier", "product", "supply_date")
    search_fields = ("supplier__name", "product__name", "product__product_code")
    ordering = ("-supply_date",)


