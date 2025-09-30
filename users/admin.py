from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_approved')
    list_filter = ('role', 'is_approved')
    search_fields = ('user__username', 'user__email')

    readonly_fields = (
        'user',
        'reset_code',
        'reset_code_expiry',
        'failed_password_attempts',
        'last_password_verified_at',
    )

    fieldsets = (
        (None, {
            "fields": (
                "user",
                "role",
                "is_approved",
                "reset_code",
                "reset_code_expiry",
                "failed_password_attempts",
                "last_password_verified_at",
                "profile_picture",
            )
        }),
    )

    def has_add_permission(self, request):
        return False 

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
