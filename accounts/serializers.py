from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from chat.models import UserProfile
import re


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2')

    def validate_username(self, value):
        # 3-30 characters
        if len(value) < 3:
            raise serializers.ValidationError(
                "Username must be at least 3 characters."
            )
        if len(value) > 30:
            raise serializers.ValidationError(
                "Username must be at most 30 characters."
            )
        # Only letters, numbers, underscores, dots
        if not re.match(r'^[a-zA-Z0-9._]+$', value):
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, dots and underscores."
            )
        # No spaces
        if ' ' in value:
            raise serializers.ValidationError("Username cannot contain spaces.")
        # Must start with a letter
        if not value[0].isalpha():
            raise serializers.ValidationError("Username must start with a letter.")
        # Check if already taken
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        return value.strip().lower()

    def validate_password(self, value):
        # Minimum 8 characters
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters."
            )
        # At least one uppercase
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter."
            )
        # At least one lowercase
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one lowercase letter."
            )
        # At least one number
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError(
                "Password must contain at least one number."
            )
        # At least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError(
                "Password must contain at least one special character (!@#$%^&*)."
            )
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_active=False  # inactive until email verified
        )
        return user


class VerifyEmailOTPSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)


class ResendEmailOTPSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()


class EmailOTPTokenObtainPairSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        'no_active_account': 'Invalid username or password.',
        'email_not_verified': 'Email not verified. Please verify your account with the OTP sent to your email.',
    }

    def validate(self, attrs):
        username = attrs.get(self.username_field)
        user = User.objects.filter(username=username).first()

        if user and not user.is_active:
            raise AuthenticationFailed(
                self.error_messages['email_not_verified'],
                code='email_not_verified',
            )

        return super().validate(attrs)


class UserProfileSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'date_joined', 'profile_picture_url')

    def get_profile_picture_url(self, obj):
        try:
            request = self.context.get('request')
            profile_picture = obj.profile.profile_picture
            if not profile_picture:
                return None
            if request:
                return request.build_absolute_uri(profile_picture.url)
            return profile_picture.url
        except UserProfile.DoesNotExist:
            return None


class ProfilePictureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('profile_picture',)
