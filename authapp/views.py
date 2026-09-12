"""
authapp/views.py

SOLID PRINCIPLE APPLIED:
- SRP: Each view class handles exactly one auth action.
  LoginView → handles login only.
  LogoutView → handles logout only.
  MeView → returns authenticated user's profile.
  ChangePasswordView → handles password change only.
  "Without SRP, a single 'AuthView' that handles login, logout, profile, and
   password change would be impossible to unit-test cleanly."

- DIP: Views depend on serializers and Django's auth abstractions, not on raw
  database queries or smtp calls directly.
  "Without DIP, testing LoginView would require a live database with seeded users."

OOP APPLIED:
- All views inherit from APIView (DRF), gaining HTTP method dispatch,
  authentication, and permission enforcement via inheritance.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
)


# =============================================================================
# Login View
# =============================================================================

class LoginView(APIView):
    """
    POST /api/auth/login/

    Authenticates a user (client or admin) and returns JWT access + refresh tokens.

    SRP — Only handles login. Token generation via Simple JWT RefreshToken.
    DIP — Depends on LoginSerializer abstraction, not on authenticate() directly.

    "Without DIP, changing from session auth to JWT would require rewriting
     the view itself instead of just swapping the token generation line."
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']

        # OOP — RefreshToken.for_user() encapsulates token creation
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# =============================================================================
# Logout View
# =============================================================================

class LogoutView(APIView):
    """
    POST /api/auth/logout/

    Blacklists the refresh token to invalidate the session.

    SRP — Only handles logout (token blacklisting).
    OCP — Switching token blacklist strategy = change this view only.

    "Without SRP, if logout logic lived inside LoginView as a DELETE action,
     adding audit logging to logout would pollute the login flow."
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required for logout."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {"detail": f"Invalid token: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


# =============================================================================
# Me (Profile) View
# =============================================================================

class MeView(APIView):
    """
    GET /api/auth/me/

    Returns the authenticated user's profile including their client_id if
    they are a client (for dashboard navigation).

    SRP — Only returns profile data; does not handle updates.
    ISP — Returns only what the client needs: id, email, name, is_admin, client_id.

    "Without ISP, returning the full Django User model with all fields exposes
     sensitive fields like last_login, password hash metadata, and is_superuser
     to every frontend request."
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =============================================================================
# Change Password View
# =============================================================================

class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/

    Allows an authenticated user to change their password.

    SRP — Only handles password changes.
    DIP — Depends on ChangePasswordSerializer for validation, not raw logic.

    "Without SRP, if password change lived inside MeView as a PATCH request,
     the view would need to distinguish between profile updates and password
     changes — violating single responsibility."
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        # Verify current password
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {"current_password": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response(
            {"detail": "Password updated successfully. Please log in again."},
            status=status.HTTP_200_OK,
        )
