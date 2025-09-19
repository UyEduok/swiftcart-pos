from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
import uuid
from django.conf import settings
from django.utils import timezone
from django.db import models, IntegrityError
from decimal import Decimal, ROUND_HALF_UP


STATUS_CHOICES = [
    ('active', 'Active'),
    ('discontinue', 'Discontinue'),
]

User = get_user_model()

# =====================
# Supporting Tables
# =====================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Unit(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class StockHistory(models.Model):
    ACTION_CHOICES = [
        ('Stock In', 'Stock In'),
        ('Sold', 'Sold'),
        ('Damaged', 'Damaged'),
        ('Returned to Supplier', 'Returned to Supplier'),
        ('Expired', 'Expired'),
        ('Lost / Stolen', 'Lost / Stolen'),
        ('Inventory Adjustment', 'Inventory Adjustment'),
    ]

    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.IntegerField()
    action_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    reference = models.CharField(max_length=100, unique=True, editable=False, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            for _ in range(10): 
                ref = f"StockHistory-{uuid.uuid4().hex[:12]}"
                if not StockHistory.objects.filter(reference=ref).exists():
                    self.reference = ref
                    break
            else:
                raise IntegrityError("Could not generate unique product reference")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action} | {self.reference} | {self.product.name} | Qty: {self.quantity}"

    class Meta:
        ordering = ['-date']


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    badge = models.CharField(max_length=50, blank=True, null=True)  # "Top Supplier", "Normal Supplier", "Low Supplier"
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)       # timestamp for creation
    updated_at = models.DateTimeField(auto_now=True)           # timestamp for updates
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='suppliers_created',
        null=True,
        blank=True
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='suppliers_updated',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name

    @staticmethod
    def update_badges():
        """
        Recalculate supplier badges based on total quantity and total amount supplied.
        Top 10 suppliers = Top Supplier
        Bottom 10 suppliers = Low Supplier
        Middle = Normal Supplier
        """

        # Annotate suppliers with total quantity and amount, treating null as 0
        suppliers_data = Supplier.objects.annotate(
            total_qty=Coalesce(Sum('supplies__quantity_supplied'), 0),
            total_amt=Coalesce(Sum('supplies__total_amount'), 0)
        ).order_by('-total_qty', '-total_amt')

        total_suppliers = suppliers_data.count()
        if total_suppliers == 0:
            return

        top_limit = 10
        low_limit = 10

        for index, supplier in enumerate(suppliers_data, start=1):
            if index <= top_limit:
                badge = "Top Supplier"
            elif index > total_suppliers - low_limit:
                badge = "Low Supplier"
            else:
                badge = "Normal Supplier"

            # Update only if badge changed (avoid unnecessary saves)
            if supplier.badge != badge:
                supplier.badge = badge
                supplier.save(update_fields=['badge'])

# =====================
# Product Table
# =====================
class Product(models.Model):
    product_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    quantity = models.PositiveIntegerField()
    min_stock_threshold = models.PositiveIntegerField()

    unit_buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    markup_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount amount per unit"
    )
    
    discount_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Minimum quantity required for discount"
    )


    unit= models.ForeignKey('Unit', on_delete=models.CASCADE)
    measurement_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    measurement_unit = models.CharField(max_length=20, blank=True)

    expiry_date = models.DateField(blank=True, null=True)
    expiry_min_threshold_days = models.PositiveIntegerField(blank=True, null=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')

    apply_vat = models.BooleanField(default=False)
    vat_value = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, default=Decimal("0.00"))

    product_image = models.ImageField(upload_to="products/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='products_created'
    )
    created_by_name = models.CharField(max_length=255, blank=True, editable=False)

    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='products_updated'
    )
    updated_by_name = models.CharField(max_length=255, blank=True, editable=False)


    def clean(self):
        # VAT validation
        if self.apply_vat and self.vat_value is None:
            raise ValidationError({"vat_value": "VAT value is required when VAT is applied."})

        if not self.apply_vat:
            self.vat_value = Decimal("0.00")

    def save(self, *args, **kwargs):

        if not self.pk and self.created_by:
            self.created_by_name = self.created_by.get_full_name() or self.created_by.username
        
        if self.pk and self.updated_by:
            self.updated_by_name = self.updated_by.get_full_name() or self.updated_by.username

        if not self.description:
            if self.measurement_value and self.measurement_unit and self.unit:
                self.description = f"{self.name} {self.measurement_value}{self.measurement_unit} {self.unit}"
        
        # Calculate markup percentage if not provided
        if not self.markup_percentage and self.unit_buying_price and self.unit_price:
            self.markup_percentage = ((self.unit_price - self.unit_buying_price) / self.unit_buying_price * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Calculate discount percentage if discount > 0
        if self.discount > 0 and self.unit_price:
            self.discount_percentage = (self.discount / self.unit_price * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.product_code})"


class ProductBatch(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=100, unique=True)  # unique globally
    quantity_left = models.PositiveIntegerField()
    expiry_date = models.DateField(blank=True, null=True)
    expiry_min_threshold_days = models.PositiveIntegerField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unknown')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="batches_created", on_delete=models.SET_NULL, null=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="batches_updated", on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - Batch {self.batch_number}"

    @property
    def status(self):
        if self.quantity_left == 0:
            return "sold out"

        if not self.expiry_date:
            return "no expiry"

        today = timezone.now().date()
        days_to_expiry = (self.expiry_date - today).days

        if days_to_expiry < 0:
            return "expired"
        elif self.expiry_min_threshold_days is not None and days_to_expiry <= self.expiry_min_threshold_days:
            return "expiring"
        else:
            return f"{days_to_expiry} days left to expiry"



class SupplierProductSupply(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplies')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='supplies')
    quantity_supplied = models.PositiveIntegerField()
    supply_date = models.DateField(auto_now_add=True) 
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-supply_date']

    def save(self, *args, **kwargs):
        if self.unit_price and self.quantity_supplied:
            self.total_amount = self.unit_price * self.quantity_supplied
        super().save(*args, **kwargs)


