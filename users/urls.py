from django.urls import path
from .views import RegisterUserView, CustomLoginView, SendResetCodeView,  upload_profile_picture
from .views import VerifyResetCodeView, PasswordChangeView, confirm_password, change_password

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='custom_login'),
    path('send-reset-code/', SendResetCodeView.as_view(), name='send_reset_code'),
    path('verify-reset-code/', VerifyResetCodeView.as_view(), name='verify-reset-code'),
    path('password-change', PasswordChangeView.as_view(), name='password-change'),
    path("confirm-password/", confirm_password, name="confirm-password"),
    path("change-password/", change_password, name="change-password"),
    path("profile-picture/",  upload_profile_picture, name="profile-picture"),   
]
