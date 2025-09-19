from django.db import models
from products.models import Product
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db.models import Sum, F, Value, IntegerField
from django.db.models.functions import Coalesce
import uuid
from django.db import IntegrityError
from django.db import models, transaction
from products.models import Product
from django.utils import timezone
import datetime


User = get_user_model()

STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
]

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(User, related_name='customers_created', on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, related_name='customers_updated', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True) 
    updated_at = models.DateTimeField(auto_now=True)

    badge = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Top Customer, Normal Customer, Low Customer"
    )

    def __str__(self):
        return self.name



    @classmethod
    def update_all_badges(cls):
        # Annotate customers with total_amount and total_qty
        annotated_customers = cls.objects.annotate(
            total_amount=Coalesce(Sum('sales__total_amount'), 0),
            total_qty=Coalesce(Sum('sales__items__quantity'), 0)
        )

        customer_data = [
            (customer, customer.total_amount + (customer.total_qty * 10))
            for customer in annotated_customers
        ]

        ranked = sorted(customer_data, key=lambda x: x[1], reverse=True)

        top_customers = [c for c, _ in ranked[:10]]
        low_customers = [c for c, _ in ranked[-10:]]

        for customer, _ in ranked:
            if customer in top_customers:
                customer.badge = "Top Customer"
            elif customer in low_customers:
                customer.badge = "Low Customer"
            else:
                customer.badge = "Normal Customer"
            customer.save()


class Sale(models.Model):
    reference = models.CharField(max_length=100, unique=True, editable=False, blank=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        related_name="sales",
        null=True,
        blank=True,
        help_text="Leave blank for anonymous customers"
    )
    total_vat = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    total_discount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_made",
        help_text="The staff member who made the sale"
    )
    staff_name = models.CharField(
        max_length=255,
        editable=False,
        help_text="Snapshot of staff name at the time of sale"
    )

    payment_type = models.CharField(
        max_length=20,
        choices=[('Cash', 'Cash'), ('Card', 'Card'), ('Transfer', 'Transfer')]
    )

    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    total_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sale_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-set staff_name when creating
        if not self.pk and self.staff:
            self.staff_name = self.staff.get_full_name() or self.staff.username
        # Generate unique reference if blank
        if not self.reference:
            for _ in range(10):
                ref = f"Sale-{uuid.uuid4().hex[:12]}"
                if not Sale.objects.filter(reference=ref).exists():
                    self.reference = ref
                    break
            else:
                raise IntegrityError("Could not generate unique sale reference")
        super().save(*args, **kwargs)

    def __str__(self):
        customer_part = self.customer.name if self.customer else "Anonymous"
        staff_part = self.staff_name or "Unknown Staff"
        return f"Sale #{self.id} - {customer_part} by {staff_part} ({self.sale_date.date()})"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    unit_price = models.DecimalField(max_digits=12, editable=False,  decimal_places=2)
    vat_value = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    discount_value = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    profit = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))
    sale_type = models.CharField(
        max_length=20,
        choices=[('sales', 'Sales'), ('damaged', 'Damaged'), ('expiring', 'Expiring')]
    )

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Sale #{self.sale.reference})"


class Receipt(models.Model):
    sale = models.OneToOneField("Sale", on_delete=models.CASCADE, related_name="receipt")
    customer = models.ForeignKey(
        "Customer", on_delete=models.SET_NULL,
        related_name="receipts", blank=True, null=True
    )
    file = models.FileField(upload_to="receipts/")  
    sales_reference = models.CharField(max_length=255) 
    receipt_number = models.BigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + datetime.timedelta(days=30)
