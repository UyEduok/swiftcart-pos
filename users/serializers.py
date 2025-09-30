from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import imghdr
import os

User = get_user_model()

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['profile_picture']
        extra_kwargs = {
            'profile_picture': {'required': False}
        }

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'password',
            'confirm_password',
            'profile',
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'password': 'Passwords do not match'})
        
        if len(attrs['password']) <= 4:
            raise serializers.ValidationError({'password': 'Password must be longer than 4 characters'})

        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({'email': 'Email is already in use'})
        
        return attrs

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {}) 
        validated_data.pop('confirm_password')

        # Capitalize first_name and last_name
        if 'first_name' in validated_data and validated_data['first_name']:
            validated_data['first_name'] = validated_data['first_name'].strip().title()

        if 'last_name' in validated_data and validated_data['last_name']:
            validated_data['last_name'] = validated_data['last_name'].strip().title()


        user = User.objects.create_user(**validated_data)

   
        profile = user.profile
        if 'profile_picture' in profile_data:
            profile.profile_picture = profile_data['profile_picture']
            profile.save()
        
        return user


class CustomLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get('identifier')
        password = attrs.get('password')

        # Try to find user by email first (contains @) or username
        try:
            if '@' in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials')

        if not check_password(password, user.password):
            raise serializers.ValidationError('Invalid credentials')

        # Account approval check (skip for staff/admin)
        if not user.profile.is_approved and not (user.is_staff or user.is_superuser):
            raise serializers.ValidationError('Account not approved yet, contact admin')

        # Role check (skip for staff/admin)
        if not user.profile.role and not (user.is_staff or user.is_superuser):
            raise serializers.ValidationError('Role not assigned yet, contact admin')

        refresh = RefreshToken.for_user(user)

        request = self.context.get('request')
        profile_picture_url = None
        if user.profile.profile_picture and hasattr(user.profile.profile_picture, 'url'):
            if request:
                profile_picture_url = request.build_absolute_uri(user.profile.profile_picture.url)
            else:
                profile_picture_url = user.profile.profile_picture.url  


        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'username': user.username,
            'email': user.email,
            'role': user.profile.role if user.profile.role else '',  
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'profile_picture': profile_picture_url, 
            'first_name': user.first_name,
            'last_name': user.last_name,
        }


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyResetCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class PasswordChangeSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)  
    password = serializers.CharField(write_only=True) 
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")
        confirm_password = data.get("confirm_password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

        # Custom password length check
        if len(password) < 5:
            raise serializers.ValidationError("Password must be at least 5 characters long.")

        # Check if passwords match
        if password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")

        # Check if new password is the same as the old one
        if user.check_password(password):
            raise serializers.ValidationError("New password cannot be the same as the old password.")

        data["user"] = user
        return data



class ConfirmPasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        request = self.context['request']
        user = request.user
        profile = user.profile

        if not user.check_password(value):
            profile.failed_password_attempts += 1
            profile.save()

            remaining = 3 - profile.failed_password_attempts

            if profile.failed_password_attempts >= 3:
                profile.failed_password_attempts = 0
                profile.save()
                # Raise non-field error for frontend logout
                raise serializers.ValidationError(
                    f"TOO_MANY_ATTEMPTS"
                )

            raise serializers.ValidationError(
                f"Incorrect password. {remaining} attempt(s) left."
            )

        # Correct password -> reset attempts
        profile.failed_password_attempts = 0
        profile.last_password_verified_at = timezone.now()
        profile.save()
        return value


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("New password must be at least 5 characters.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        profile = user.profile

        # Check old password verification timestamp
        last_verified = getattr(profile, "last_password_verified_at", None)
        if not last_verified:
            raise serializers.ValidationError("Old password verification required before changing password.")

        if timezone.now() - last_verified > timedelta(minutes=4):
            raise serializers.ValidationError("Old password verification expired. Please verify again.")

        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        # Check if new_password and confirm_password match
        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Check that new password is not the same as old password
        if user.check_password(new_password):
            raise serializers.ValidationError({"new_password": "New password cannot be the same as the old password."})

        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data["new_password"])
        user.save()

        # Clear the verification timestamp
        profile = user.profile
        profile.last_password_verified_at = None
        profile.save()

        return user


class ProfilePictureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['profile_picture']

    def validate_profile_picture(self, value):
        # 1. Check extension
        ext = os.path.splitext(value.name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if ext not in allowed_extensions:
            raise serializers.ValidationError("Unsupported file extension. Use JPG, PNG, GIF, or WEBP.")

        # 2. Check actual file content (not just extension)
        file_type = imghdr.what(value)
        if file_type not in ['jpeg', 'png', 'gif', 'webp']:
            raise serializers.ValidationError("Uploaded file is not a valid image.")

        return value

    def update(self, instance, validated_data):
        instance.profile_picture = validated_data.get('profile_picture', instance.profile_picture)
        instance.save()
        return instance



