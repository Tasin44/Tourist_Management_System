"""
livable/urls.py

SOLID PRINCIPLES:
- SRP: URL routing has one job — map paths to views. No business logic here.
- OCP: New endpoints are added by appending path() calls. Existing routes are never modified.
  "Without OCP, every new endpoint would require editing this file's internals —
   risking accidentally breaking existing route patterns via typos or ordering changes."

Full URL Map:
  ── Admin: Schedule ──────────────────────────────────────────────
  POST   /api/admin/today/{user_id}/                  AdminTodayCreateView
  PUT    /api/admin/today/item/{item_id}/              AdminScheduleItemView
  DELETE /api/admin/today/item/{item_id}/              AdminScheduleItemView

  ── Admin: City Tests ────────────────────────────────────────────
  POST   /api/admin/city-tests/                        AdminCityTestListCreateView
  PUT    /api/admin/city-tests/{test_id}/              AdminCityTestDetailView
  DELETE /api/admin/city-tests/{test_id}/              AdminCityTestDetailView
  GET    /api/admin/city-tests/submissions/            AdminSubmissionsView

  ── Client (PWA): Schedule ───────────────────────────────────────
  GET    /api/app/today/                               ClientTodayView

  ── Client (PWA): City Tests ─────────────────────────────────────
  GET    /api/app/city-tests/categories/               ClientCategoryListView
  GET    /api/app/city-tests/categories/{category_id}/ ClientCategoryDetailView
  GET    /api/app/city-tests/{test_id}/                ClientCityTestDetailView
  POST   /api/app/city-tests/{test_id}/save/           ClientSaveCityTestView

  ── Client (PWA): Solo Micro-Tests ───────────────────────────────
  GET    /api/app/solo-micro-tests/                    SoloMicroTestListView
"""

from django.urls import path

from livable.views.admin_views import (
    AdminTodaysListView,
    AdminTodayDetailView,
    AdminTodayCreateView,
    AdminScheduleItemView,
    AdminCityTestListCreateView,
    AdminCityTestDetailView,
    AdminSubmissionsView,
)
from livable.views.client_views import (
    ClientTodayView,
    ClientCategoryListView,
    ClientCategoryDetailView,
    ClientCityTestDetailView,
    ClientSaveCityTestView,
    ClientSubmissionsView,
    SoloMicroTestListView,
)

app_name = 'livable'

urlpatterns = [
    # ── Admin: Schedule ───────────────────────────────────────────────────────
    path(
        'admin/todays/',
        AdminTodaysListView.as_view(),
        name='admin-todays-list',
    ),
    path(
        'admin/todays/<int:schedule_id>/',
        AdminTodayDetailView.as_view(),
        name='admin-today-detail',
    ),
    path(
        'admin/today/<int:user_id>/',
        AdminTodayCreateView.as_view(),
        name='admin-today-create',
    ),
    path(
        'admin/today/item/<uuid:item_id>/',
        AdminScheduleItemView.as_view(),
        name='admin-schedule-item',
    ),

    # ── Admin: City Tests ─────────────────────────────────────────────────────
    # NOTE: 'submissions/' must come BEFORE '<str:test_id>/' to avoid test_id
    # capturing the literal string "submissions"
    # OCP: this ordering concern is documented here, not scattered in views.
    path(
        'admin/city-tests/submissions/',
        AdminSubmissionsView.as_view(),
        name='admin-city-test-submissions',
    ),
    path(
        'admin/city-tests/',
        AdminCityTestListCreateView.as_view(),
        name='admin-city-test-list-create',
    ),
    path(
        'admin/city-tests/<str:test_id>/',
        AdminCityTestDetailView.as_view(),
        name='admin-city-test-detail',
    ),

    # ── Client (PWA): Schedule ────────────────────────────────────────────────
    path(
        'app/today/',
        ClientTodayView.as_view(),
        name='client-today',
    ),

    # ── Client (PWA): City Tests ──────────────────────────────────────────────
    path(
        'app/city-tests/submissions/',
        ClientSubmissionsView.as_view(),
        name='client-submissions',
    ),
    path(
        'app/city-tests/categories/',
        ClientCategoryListView.as_view(),
        name='client-category-list',
    ),
    path(
        'app/city-tests/categories/<str:category_id>/',
        ClientCategoryDetailView.as_view(),
        name='client-category-detail',
    ),
    path(
        'app/city-tests/<str:test_id>/save/',
        ClientSaveCityTestView.as_view(),
        name='client-city-test-save',
    ),
    path(
        'app/city-tests/<str:test_id>/',
        ClientCityTestDetailView.as_view(),
        name='client-city-test-detail',
    ),

    # ── Client (PWA): Solo Micro-Tests ────────────────────────────────────────
    path(
        'app/solo-micro-tests/',
        SoloMicroTestListView.as_view(),
        name='client-solo-micro-tests',
    ),
]
