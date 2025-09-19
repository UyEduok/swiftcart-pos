from django.shortcuts import render
from rest_framework.views import APIView
from .serializers import UserSerializer
from rest_framework.response import Response
from rest_framework import status, serializers
from .serializers import CustomLoginSerializer
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .serializers import EmailSerializer
from .utils import generate_reset_code, send_reset_code_email
from .serializers import VerifyResetCodeSerializer, ConfirmPasswordSerializer, ChangePasswordSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.views import View
from django.http import JsonResponse
import json
from rest_framework import status
from .serializers import PasswordChangeSerializer
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .serializers import ProfilePictureSerializer
from .serializers import ProfileSerializer


class RegisterUserView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'User registered successfully. Await admin approval.'}, status=201)
        return Response(serializer.errors, status=400)

class CustomLoginView(APIView):
    def post(self, request):
        serializer = CustomLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendResetCodeView(APIView):
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'email': 'No user found with this email.'}, status=status.HTTP_404_NOT_FOUND)

        # Generate and store code
        code = generate_reset_code()
        profile = user.profile
        profile.reset_code = code
        profile.reset_code_expiry = timezone.now() + timedelta(minutes=6, seconds=10)
        profile.save()

        # Send code to email
        send_reset_code_email(user.email, code)

        return Response({'message': 'Reset code sent to email.'}, status=status.HTTP_200_OK)


class VerifyResetCodeView(APIView):
    def post(self, request):
        serializer = VerifyResetCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'No user found with this email.'}, status=status.HTTP_404_NOT_FOUND)

        profile = user.profile

        # Check if code matches
        if profile.reset_code != code:
            return Response({'error': 'Invalid code.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if code is expired
        if timezone.now() > profile.reset_code_expiry:
            return Response({'error': 'Code has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Code verified successfully.'}, status=status.HTTP_200_OK)


class PasswordChangeView(View):
    User = get_user_model()
    def post(self, request):
        try:
            data = json.loads(request.body)
            email = data.get("email")
            password = data.get("password")
            confirm_password = data.get("confirmPassword")

            # 1️Validate required fields
            if not email or not password or not confirm_password:
                return JsonResponse({"error": "All fields are required."}, status=400)

            #  Ensure new password matches confirm
            if password != confirm_password:
                return JsonResponse({"error": "Passwords do not match."}, status=400)

            # Find the user
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return JsonResponse({"error": "User not found."}, status=404)

            # Ensure the new password is not the same as the old one
            if check_password(password, user.password):
                return JsonResponse({"error": "New password cannot be the same as your previous password."}, status=400)

            # Set and save new password
            user.set_password(password)
            user.save()

            return JsonResponse({"message": "Password changed successfully."}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            new_password = serializer.validated_data['password']
            
            user.set_password(new_password)
            user.save()

            return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TokenValidateThrottle(UserRateThrottle):
    rate = '10/minute' 

class TokenValidateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TokenValidateThrottle]

    def get(self, request):
        return Response({"detail": "Token is valid"}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_password(request):
    serializer = ConfirmPasswordSerializer(data=request.data, context={'request': request})

    try:
        serializer.is_valid(raise_exception=True)
    except serializers.ValidationError as e:

        if "TOO_MANY_ATTEMPTS" in str(e.detail):
            return Response(
                {"detail": "Too many failed attempts. You have been logged out."},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response({"old_password": e.detail}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"detail": "Password verified successfully."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    profile = request.user.profile
    serializer = ProfilePictureSerializer(profile, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()

        profile_picture_url = None
        if profile.profile_picture and hasattr(profile.profile_picture, 'url'):
            profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)

        return Response(
            {
                "detail": "Profile picture updated successfully.",
                "profile_picture": profile_picture_url 
            },
            status=status.HTTP_200_OK
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

