from django.db import models
from django.contrib.auth.models import User
from products.models import Product
import uuid
from django.db import IntegrityError


class ExpiringProduct(models.Model):
    reference = models.CharField(max_length=100, unique=True, editable=False, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_code = models.CharField(max_length=100, editable=False, unique=True)
    product_name = models.CharField(max_length=255, editable=False)
    initial_unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    resale_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    loss_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False)


    # Tracking fields
    staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name="expiring_created")
    staff_name = models.CharField(max_length=255, editable=False)
    last_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="expiring_updated")
    last_updated_name = models.CharField(max_length=255, editable=False, blank=True)

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(blank=True, null=True)

    note = models.TextField(blank=True, null=True)
    description = models.TextField(editable=False, blank=True, null=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_date']

    def save(self, *args, **kwargs):
        # Pull details from Product when creating
        if not self.pk and self.product:
            self.description = self.product.description + " (EP)"
            self.expiry_date = getattr(self.product, "expiry_date", None) 

        # If quantity is zero, delete instead of saving
        if self.quantity == 0:
            if self.pk:  
                self.delete()
            return

        # Calculate loss value
        self.loss_value = (self.initial_unit_price - self.resale_price) * self.quantity

        # Mirror staff name
        if self.staff and not self.staff_name:
            self.staff_name = self.staff.get_full_name() or self.staff.username

        # Mirror last updated by name
        if self.last_updated_by:
            self.last_updated_name = self.last_updated_by.get_full_name() or self.last_updated_by.username

        if not self.reference:
            for _ in range(10): 
                ref = f"ExpiringProduct-{uuid.uuid4().hex[:12]}"
                if not ExpiringProduct.objects.filter(reference=ref).exists():
                    self.reference = ref
                    break
            else:
                raise IntegrityError("Could not generate unique product reference")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} ({self.product_code})"


class DamageProduct(models.Model):
    reference = models.CharField(max_length=100, unique=True, editable=False, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_code = models.CharField(max_length=100, unique=True, editable=False)
    product_name = models.CharField(max_length=255, editable=False)
    initial_unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    resale_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    loss_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    # Tracking fields
    staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name="damage_created")
    staff_name = models.CharField(max_length=255, editable=False)
    last_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="damage_updated")
    last_updated_name = models.CharField(max_length=255, editable=False, blank=True)
    is_approved = models.BooleanField(default=False)
    description = models.TextField(editable=False, blank=True, null=True)

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(blank=True, null=True)


    note = models.TextField(blank=True, null=True)
    description = models.TextField(editable=False, blank=True, null=True)

    class Meta:
        ordering = ['-created_date']

    def save(self, *args, **kwargs):
        # Pull details from Product when creating
        if not self.pk and self.product:
            self.description = self.product.description + " (DP)"

        # Calculate loss value
        self.loss_value = (self.initial_unit_price - self.resale_price) * self.quantity

        # Mirror staff name
        if self.staff and not self.staff_name:
            self.staff_name = self.staff.get_full_name() or self.staff.username

        # Mirror last updated by name
        if self.last_updated_by:
            self.last_updated_name = self.last_updated_by.get_full_name() or self.last_updated_by.username

        # If quantity is zero, delete instead of saving
        if self.quantity == 0:
            if self.pk:  
                self.delete()
            return

        if not self.reference:
            for _ in range(10): 
                ref = f"DamageProduct-{uuid.uuid4().hex[:12]}"
                if not DamageProduct.objects.filter(reference=ref).exists():
                    self.reference = ref
                    break
            else:
                raise IntegrityError("Could not generate unique product reference")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} ({self.product_code})"
