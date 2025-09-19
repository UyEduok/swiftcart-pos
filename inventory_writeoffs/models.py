from django.db import models
from django.contrib.auth.models import User
from products.models import Product
import uuid
from django.db import IntegrityError

def generate_unique_reference():
    while True:
        ref = f"SALE-{uuid.uuid4().hex[:8].upper()}"
        if not Sale.objects.filter(reference=ref).exists():
            return ref


class InventoryWriteOff(models.Model):
    REASONS = [
        ('Damaged', 'Damaged'),
        ('Return to supplier', 'Returned to Supplier'),
        ('Expired', 'Expired'),
        ('Lost', 'Lost / Stolen'),
        ('Adjustment', 'Inventory Adjustment'),
    ]

    reference = models.CharField(max_length=100, unique=True, editable=False, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = models.TextField(editable=False)  
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=REASONS)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    loss_value = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    note = models.TextField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='writeoff_created')
    created_by_name = models.CharField(max_length=255, editable=False)

    def save(self, *args, **kwargs):
        # Auto description from Product
        if self.product:
            self.description = getattr(self.product, 'description', '') or self.product.name
            self.unit_price = getattr(self.product, 'unit_price', 0)

        # Calculate loss value
        self.loss_value = (self.unit_price or 0) * self.quantity

        # Mirror created_by name
        if self.created_by:
            self.created_by_name = f"{self.created_by.first_name} {self.created_by.last_name}".strip() or self.created_by.username

        if not self.reference:
            for _ in range(10): 
                ref = f"InventoryWriteOff-{uuid.uuid4().hex[:12]}"
                if not InventoryWriteOff.objects.filter(reference=ref).exists():
                    self.reference = ref
                    break
            else:
                raise IntegrityError("Could not generate unique product reference")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.get_reason_display()} - {self.quantity}"
