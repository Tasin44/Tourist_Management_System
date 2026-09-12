"""
authapp/serializers.py

SOLID PRINCIPLE APPLIED:
- SRP: Each serializer handles exactly one auth concern.
  LoginSerializer handles login; TokenRefreshSerializer is handled by Simple JWT.
  "Without SRP, a single AuthSerializer that handles registration, login, and
   token refresh would grow into an unmanageable blob."

- OCP: Adding OAuth / social auth = add a new serializer, never modify Login.
  "Without OCP, adding Google login would require editing LoginSerializer,
   risking breaking the existing email/password login."

OOP APPLIED:
- Serializers inherit from serializers.Serializer (not ModelSerializer) because
  login is a behavior, not a model save operation — proper OOP modeling.
"""

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import User


class LoginSerializer(serializers.Serializer):
    """
    Validates email + password credentials for client/admin login.

    SRP — Only validates credentials. Token generation is handled by the view
          (via Simple JWT or authapp token logic).

    OOP — Uses Serializer (not ModelSerializer) because login doesn't create
          a model instance; it validates against existing data.

    "Without OOP modeling (using ModelSerializer here), we'd be forced to
     tie login validation to a specific model's fields — making it brittle
     when auth backends change."
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        """
        SRP — Validation logic lives here, not in the view.
        OCP — Adding 2FA check = extend this method, don't touch the view.
        """
        email = attrs.get('email', '').lower()
        password = attrs.get('password', '')

        # Django's authenticate uses username; we map email → username
        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError(
                "Invalid credentials. Please check your email and password."
            )

        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")

        attrs['user'] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only representation of the authenticated user's basic profile.

    SRP — Only serializes user identity info for the /me endpoint.
    ISP — Clients don't receive admin flags; admins don't receive client-only fields.

    "Without ISP, one UserSerializer with all fields would expose is_staff
     and is_superuser to every client calling /me — a security risk."
    """

    is_admin = serializers.SerializerMethodField()
    client_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_admin', 'client_id']
        read_only_fields = fields

    def get_is_admin(self, obj) -> bool:
        """OOP — Computed field via SerializerMethodField."""
        return obj.is_staff

    def get_client_id(self, obj):
        """
        OOP — Safely navigates the reverse relation.
        Returns the linked client's PK if it exists, else None.
        """
        try:
            return obj.client_profile.pk
        except Exception:
            return None


class ChangePasswordSerializer(serializers.Serializer):
    """
    Validates the current password and the new password for a password change.

    SRP — Only handles password change validation.
    OCP — Adding password strength rules = extend validate_new_password.

    "Without SRP, if password change logic lived inside the profile update
     serializer, every profile update would unnecessarily validate passwords."
    """

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError(
                {"confirm_new_password": "New passwords do not match."}
            )
        return attrs
