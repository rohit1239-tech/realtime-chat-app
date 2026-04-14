import random
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from chat.models import UserProfile

from .models import EmailOTP
from .serializers import (
    EmailOTPTokenObtainPairSerializer,
    ProfilePictureSerializer,
    RegisterSerializer,
    ResendEmailOTPSerializer,
    UserProfileSerializer,
    VerifyEmailOTPSerializer,
)


OTP_EXPIRY_MINUTES = 10
logger = logging.getLogger(__name__)


class OTPDeliveryError(Exception):
    pass


def send_email_verification_otp(user):
    EmailOTP.objects.filter(
        user=user,
        purpose=EmailOTP.PURPOSE_EMAIL_VERIFICATION,
        is_used=False,
    ).update(is_used=True)

    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    EmailOTP.objects.create(
        user=user,
        purpose=EmailOTP.PURPOSE_EMAIL_VERIFICATION,
        code=otp_code,
        expires_at=expires_at,
    )

    from_email = (
        settings.DEFAULT_FROM_EMAIL
        or settings.EMAIL_HOST_USER
        or 'noreply@chatapp.com'
    )

    try:
        send_mail(
            subject='Your ChatApp verification OTP',
            message=(
                f"Hi {user.username}!\n\n"
                f"Your ChatApp email verification OTP is: {otp_code}\n\n"
                f"This OTP expires in {OTP_EXPIRY_MINUTES} minutes.\n"
                "If you didn't create this account, you can ignore this email."
            ),
            from_email=from_email,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception(
            "Failed to send verification OTP email for user '%s'.",
            user.username,
        )
        raise OTPDeliveryError(
            "We couldn't send the verification email right now. "
            "Please try again in a few minutes."
        ) from exc


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
                send_email_verification_otp(user)
        except OTPDeliveryError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response({
            "message": "Account created. We've sent a 6-digit OTP to your email.",
            "email": user.email,
        }, status=status.HTTP_201_CREATED)


class VerifyEmailOTPView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = VerifyEmailOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username'].strip()
        email = serializer.validated_data['email'].strip().lower()
        otp = serializer.validated_data['otp'].strip()

        try:
            user = User.objects.get(username=username, email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid username, email, or OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp_record = EmailOTP.objects.filter(
            user=user,
            purpose=EmailOTP.PURPOSE_EMAIL_VERIFICATION,
            code=otp,
            is_used=False,
        ).first()

        if not otp_record:
            return Response(
                {"error": "Invalid username, email, or OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp_record.expires_at < timezone.now():
            return Response(
                {"error": "OTP expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])
        user.is_active = True
        user.save(update_fields=['is_active'])

        return Response(
            {"message": "Email verified successfully! You can now login."},
            status=status.HTTP_200_OK
        )


class ResendEmailOTPView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = ResendEmailOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username'].strip()
        email = serializer.validated_data['email'].strip().lower()
        user = User.objects.filter(username=username, email__iexact=email).first()

        if not user:
            return Response(
                {"error": "No account found for this username and email."},
                status=status.HTTP_404_NOT_FOUND
            )

        if user.is_active:
            return Response(
                {"message": "This email is already verified. You can login now."},
                status=status.HTTP_200_OK
            )

        try:
            send_email_verification_otp(user)
        except OTPDeliveryError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(
            {"message": "A new OTP has been sent to your email."},
            status=status.HTTP_200_OK
        )


class LoginView(TokenObtainPairView):
    serializer_class = EmailOTPTokenObtainPairSerializer


class LogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Logged out successfully."},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = ProfilePictureSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = UserProfileSerializer(
            request.user,
            context={'request': request},
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
