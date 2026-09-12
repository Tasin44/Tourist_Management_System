"""
authapp/urls.py

SRP: URL routing for the auth app — maps paths to views only, no logic.
OCP: New auth endpoints (e.g., /forgot-password/) are added by appending here.

URL Structure:
  POST /api/auth/login/           → LoginView
  POST /api/auth/logout/          → LogoutView
  GET  /api/auth/me/              → MeView
  POST /api/auth/change-password/ → ChangePasswordView
  POST /api/auth/token/refresh/   → TokenRefreshView (Simple JWT)
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView, ChangePasswordView

app_name = 'authapp'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    # Simple JWT built-in token refresh (OCP: added without touching LoginView)
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
