"""
clients/urls.py

SOLID PRINCIPLE APPLIED:
- SRP: URL routing has one job — map URL patterns to views. No business logic here.
- OCP: New endpoints are added by appending new path() calls, never by editing
  existing ones.
  "Without OCP, adding a new trip endpoint would require modifying existing
   patterns — risking breaking other route matches."

URL Structure:
  POST   /api/clients/create/                        → CreateClientView
  GET    /api/clients/                               → ListClientsView
  POST   /api/clients/<client_id>/trips/             → CreateTripView
  GET    /api/clients/<client_id>/trips/<trip_id>/   → ClientTripDetailView (client+admin)
  PUT    /api/clients/<client_id>/trips/<trip_id>/   → ClientTripDetailView (admin only)
  DELETE /api/clients/<client_id>/trips/<trip_id>/   → ClientTripDetailView (admin only)
  GET    /api/trips/                                 → ListAllTripsView (admin)
  GET    /api/trips/upcoming/                        → UpcomingTripsView (admin)
  GET    /api/trips/recent/                          → RecentTripsView (admin)
  GET    /api/me/dashboard/                          → ClientDashboardView (client)
  POST   /api/anonymous/book/                        → AnonymousBookingCreateView
  GET    /api/anonymous/book/                        → AnonymousBookingListView (admin)
  POST   /api/clients/<client_id>/financial-profile/ → CreateFinancialProfileView
  POST   /api/clients/<client_id>/lifestyle-alignment/ → CreateLifestyleAlignmentView
"""

from django.urls import path

from .views import (
    CreateClientView,
    ListClientsView,
    ClientTargetDestinationsView,
    CreateTripView,
    ClientTripDetailView,
    ListAllTripsView,
    UpcomingTripsView,
    RecentTripsView,
    ClientDashboardView,
    ClientMyTripsView,
    AnonymousBookingCreateView,
    AnonymousBookingListView,
    CreateFinancialProfileView,
    CreateLifestyleAlignmentView,
)

app_name = 'clients'

urlpatterns = [
    # ── Client endpoints ──────────────────────────────────────────────────────
    path('clients/create/', CreateClientView.as_view(), name='create-client'),
    path('clients/', ListClientsView.as_view(), name='list-clients'),
    path('clients/target_destination/', ClientTargetDestinationsView.as_view(), name='target-destinations'),

    # ── Trip endpoints ────────────────────────────────────────────────────────
    path(
        'clients/<int:client_id>/trips/',
        CreateTripView.as_view(),
        name='create-trip',
    ),
    path(
        'clients/<int:client_id>/trips/<int:pk>/',
        ClientTripDetailView.as_view(),
        name='trip-detail',
    ),
    path('trips/', ListAllTripsView.as_view(), name='list-all-trips'),
    path('trips/upcoming/', UpcomingTripsView.as_view(), name='upcoming-trips'),
    path('trips/recent/', RecentTripsView.as_view(), name='recent-trips'),

    # ── Client dashboard (client-facing) ─────────────────────────────────────
    path('me/dashboard/', ClientDashboardView.as_view(), name='client-dashboard'),
    path('me/trips/', ClientMyTripsView.as_view(), name='client-my-trips'),

    # ── Anonymous booking ─────────────────────────────────────────────────────
    path('anonymous/book/', AnonymousBookingCreateView.as_view(), name='anonymous-book-create'),
    path('anonymous/book/list/', AnonymousBookingListView.as_view(), name='anonymous-book-list'),

    # ── Financial profile ─────────────────────────────────────────────────────
    path(
        'clients/<int:client_id>/financial-profile/',
        CreateFinancialProfileView.as_view(),
        name='financial-profile',
    ),

    # ── Lifestyle alignment ───────────────────────────────────────────────────
    path(
        'clients/<int:client_id>/lifestyle-alignment/',
        CreateLifestyleAlignmentView.as_view(),
        name='lifestyle-alignment',
    ),
]
