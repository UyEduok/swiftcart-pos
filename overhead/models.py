from django.db import models
from django.contrib.auth.models import User


class Overhead(models.Model):
    OVERHEAD_TYPE_CHOICES = [
        ("capital", "Capital/Non-Recurring Overhead"),
        ("recurring", "Recurring/Recurrent Overhead"),
    ]

    CATEGORY_CHOICES = [
        # Recurring
        ("salaries", "Salaries & Wages"),
        ("rent", "Office/Shop Rent"),
        ("insurance", "Insurance"),
        ("utilities", "Utilities (Electricity, Water, etc.)"),
        # Capital
        ("equipment", "Equipment Purchase"),
        ("repair", "Repair or Maintenance"),
        ("license", "Annual Licence Renewal"),
        ("marketing", "Marketing Campaign"),
        # Common option
        ("others", "Others"),
    ]

    overhead_type = models.CharField(
        max_length=20, choices=OVERHEAD_TYPE_CHOICES
    )
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES
    )

    # Duration for fixed/recurrent overhead
    duration = models.IntegerField(
        choices=[(i, f"{i} month{'s' if i > 1 else ''}") for i in range(1, 13)],
        blank=True,
        null=True,
        help_text="Select number of months (1–12) for fixed/recurrent overhead"
    )

    # Amount
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  
        null=True,
        blank=True,
        related_name="created_overheads"
    )
    created_by_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stores creator’s name in case the user is deleted"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-generate description if it's blank and category is not "others"
        if not self.description and self.category != "others":
            overhead_type_display = self.get_overhead_type_display()
            if "/" in overhead_type_display:
                overhead_type_display = overhead_type_display.split("/")[0]

            category_display = dict(self.CATEGORY_CHOICES).get(self.category, self.category)
            if category_display and "/" in category_display:
                category_display = category_display.split("/")[0]

            if self.created_by_name:
                self.description = (
                    f"{overhead_type_display} overhead for {category_display} payment, "
                    f"recorded by {self.created_by_name}"
                )
            else:
                self.description = f"{overhead_type_display} for {category_display} payment"

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.get_overhead_type_display()} - {self.amount}"
