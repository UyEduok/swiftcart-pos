from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    ROLE_CHOICES = [
        ('inventory', 'Inventory Person'),
        ('cashier', 'Cashier'),
        ('analyst', 'Analyst'),
        ('manager', 'Manager'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg', blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True)
    is_approved = models.BooleanField(default=False)
    reset_code = models.CharField(max_length=10, blank=True, null=True)
    reset_code_expiry = models.DateTimeField(blank=True, null=True)
    failed_password_attempts = models.PositiveIntegerField(default=0)
    last_password_verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"
