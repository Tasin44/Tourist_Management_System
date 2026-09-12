"""
URL configuration for aamyproject.

SOLID PRINCIPLE APPLIED:
- SRP: Root URL config has one job — aggregate app-level URL namespaces.
- OCP: New apps are added by including their urls.py here; existing routes
  are never modified.
  "Without OCP, every new API endpoint would require editing this file AND
   risking breaking existing URL patterns."
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django admin panel
    path('admin/', admin.site.urls),

    # Auth app: login, logout, me, change-password, token refresh
    path('api/auth/', include('authapp.urls', namespace='authapp')),

    # Clients app: clients, trips, anonymous booking, financial profile, lifestyle
    path('api/', include('clients.urls', namespace='clients')),

    # Livable app: today schedule, city tests, solo micro-tests
    path('api/', include('livable.urls', namespace='livable')),
]
