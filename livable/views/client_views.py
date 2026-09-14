"""
livable/views/client_views.py

All client-facing (PWA) API views for the livable app.

SOLID PRINCIPLES APPLIED:
──────────────────────────────────────────────────────────────────────────────
S — Single Responsibility:
    Each view handles exactly one endpoint.
    ClientTodayView          → GET /app/today
    ClientCategoryListView   → GET /app/city-tests/categories
    ClientCategoryDetailView → GET /app/city-tests/categories/{category_id}
    ClientCityTestDetailView → GET /app/city-tests/{test_id}
    ClientSaveCityTestView   → POST /app/city-tests/{test_id}/save
    SoloMicroTestListView    → GET /app/solo-micro-tests

    "Without SRP, a single 'ClientAppView' with a 'type' query param to switch
     between today/categories/tests would be untestable and unmaintainable —
     every test case would need to simulate a different query parameter."

O — Open/Closed:
    All views are closed for modification. Adding the "weekly view" endpoint
    means creating a new ClientWeekView class, not editing ClientTodayView.

I — Interface Segregation:
    Client views use client-specific serializers that exclude admin-only data.
    "Without ISP, using the same AdminCityTestReadSerializer for clients would
     expose created_at, updated_at, and order — admin metadata clients don't need."

D — Dependency Inversion:
    Views depend on serializer abstractions. Swapping the serializer (e.g.,
    adding a field) requires zero view changes.

OOP APPLIED:
    • _get_client_from_request — private helper encapsulates client lookup from JWT.
    • All views inherit APIView; authentication is inherited, not repeated.
    • Serializer context={'client': client} passes the current user as an
      abstract dependency into nested serializers (DIP in action).
"""

from django.utils.timezone import now as tz_now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from clients.models import Client
from livable.models import (
    DailySchedule,
    CityTestCategory,
    CityTest,
    CityTestSubmission,
    SoloMicroTestGroup,
)
from livable.serializers import (
    ClientDailyScheduleSerializer,
    ClientCategorySerializer,
    ClientCategoryDetailSerializer,
    ClientCityTestDetailSerializer,
    CityTestSubmissionWriteSerializer,
    SoloMicroTestGroupSerializer,
)


# =============================================================================
# Shared Helper
# SRP: One job — resolve the authenticated user to a Client instance.
# DIP: Views call this helper rather than duplicating client-lookup logic.
# =============================================================================

def get_client_from_request(request):
    """
    Resolves the authenticated User to their linked Client profile.

    SRP — Has one responsibility: map User → Client.
    DIP — Views depend on this function abstraction, not on the reverse FK pattern.

    "Without this helper, every client view would repeat:
       try: client = request.user.client_profile
       except Client.DoesNotExist: return 404
     — repeating the same pattern in 6+ views, all needing simultaneous fixes
     if the profile relation ever changes."

    Returns:
        (client, None) on success, (None, Response(404)) on failure.
    """
    try:
        return request.user.client_profile, None
    except Client.DoesNotExist:
        err = Response(
            {"detail": "No client profile found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )
        return None, err


# =============================================================================
# SCHEDULE / TODAY — Client Views
# =============================================================================

class ClientTodayView(APIView):
    """
    GET /api/app/today
    Query: ?date=YYYY-MM-DD  (optional, defaults to today)

    Returns the authenticated client's schedule for the given date.

    SRP — Only serves the today/schedule view.
    ISP — Uses ClientDailyScheduleSerializer which exposes ONLY the client-facing
          fields (no admin fields like 'order', 'host_name' in admin context).
    DIP — Depends on ClientDailyScheduleSerializer, not raw model data.

    "Without ISP, if we returned raw DailySchedule + ScheduleItem data directly,
     the PWA would receive internal fields like 'item.order' and 'schedule.id'
     that break the client contract when internal IDs change."
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        client, err = get_client_from_request(request)
        if err:
            return err

        # Default date = today; allow override via ?date=
        date_param = request.query_params.get('date')
        if date_param:
            try:
                from datetime import date
                target_date = date.fromisoformat(date_param)
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target_date = tz_now().date()

        try:
            schedule = (
                DailySchedule.objects
                .prefetch_related('items')
                .get(client=client, date=target_date)
            )
        except DailySchedule.DoesNotExist:
            return Response(
                {"detail": f"No schedule found for {target_date}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ClientDailyScheduleSerializer(schedule)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =============================================================================
# CITY TESTS — Client Views
# =============================================================================

class ClientCategoryListView(APIView):
    """
    GET /api/app/city-tests/categories

    Returns all city test categories with saved_count for this client.

    SRP — Only serves the category list view.
    ISP — Client sees id, name, description, saved_count. Admin metadata excluded.
    DIP — Passes client via serializer context (DIP: serializer gets the
          dependency injected, not hardcoded).

    "Without DIP, if saved_count was computed inside the view and then manually
     injected into each category dict, adding a new computed field would require
     editing both the view AND the dict-building logic — coupled and fragile."
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        client, err = get_client_from_request(request)
        if err:
            return err

        categories = CityTestCategory.objects.order_by('order')

        # DIP: inject client as context; serializer computes saved_count internally
        serializer = ClientCategorySerializer(
            categories,
            many=True,
            context={'client': client},  # DIP: dependency injected via context
        )
        return Response({"categories": serializer.data}, status=status.HTTP_200_OK)


class ClientCategoryDetailView(APIView):
    """
    GET /api/app/city-tests/categories/{category_id}

    Returns a category with all its tests and completion status per test.

    SRP — Only serves category-detail. The list view is a separate class.
    OCP — Adding a 'progress_percentage' field = extend the serializer only.

    "Without OCP, adding progress_percentage would require editing this view
     AND the ClientCategoryDetailSerializer — two coupled change points.
     With OCP, only the serializer changes."
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, category_id):
        client, err = get_client_from_request(request)
        if err:
            return err

        try:
            category = CityTestCategory.objects.prefetch_related('tests').get(pk=category_id)
        except CityTestCategory.DoesNotExist:
            return Response(
                {"detail": f"Category '{category_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ClientCategoryDetailSerializer(
            category,
            context={'client': client},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClientCityTestDetailView(APIView):
    """
    GET /api/app/city-tests/{test_id}

    Returns full details for one city test, plus the client's previous submission.

    SRP — Only serves test detail. List/categories are separate classes.
    ISP — Returns previous_submission only for the current client (no cross-client data).
    DIP — Injects client via context so the serializer resolves previous_submission.

    "Without DIP, the view would fetch the previous submission and manually
     pass it into a pre-built dict — tightly coupling view routing with
     data-fetch logic and making both untestable in isolation."
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, test_id):
        client, err = get_client_from_request(request)
        if err:
            return err

        try:
            test = CityTest.objects.select_related('category').get(pk=test_id)
        except CityTest.DoesNotExist:
            return Response(
                {"detail": f"City Test '{test_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ClientCityTestDetailSerializer(
            test,
            context={'client': client},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClientSaveCityTestView(APIView):
    """
    POST /api/app/city-tests/{test_id}/save

    Client saves/completes a city test by submitting notes and questions.
    Uses update_or_create so re-submitting overwrites the previous submission.

    SRP — Only handles submission creation/update.
    OCP — Adding new submission fields (e.g., photos) = extend serializer only.
    DIP — Depends on CityTestSubmissionWriteSerializer for validation.

    "Without DIP, if validation lived inside this view, adding a min-length
     check to 'notes' would require editing the view — mixing routing logic
     with validation logic."
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, test_id):
        client, err = get_client_from_request(request)
        if err:
            return err

        try:
            test = CityTest.objects.select_related('category').get(pk=test_id)
        except CityTest.DoesNotExist:
            return Response(
                {"detail": f"City Test '{test_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CityTestSubmissionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # OOP: update_or_create — idempotent, handles both first-time and re-submission
        CityTestSubmission.objects.update_or_create(
            client=client,
            test=test,
            defaults=serializer.validated_data,
        )

        # Return updated saved_count for this category
        new_saved_count = CityTestSubmission.objects.filter(
            client=client,
            test__category=test.category,
        ).count()

        return Response(
            {
                "success": True,
                "test_id": test_id,
                "category_id": test.category_id,
                "new_saved_count": new_saved_count,
                "message": "Test completed and saved",
            },
            status=status.HTTP_200_OK,
        )


class ClientSubmissionsView(APIView):
    """
    GET /api/app/city-tests/submissions/

    Returns all city test submissions for the authenticated client.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        client, err = get_client_from_request(request)
        if err:
            return err
            
        # We can reuse the admin serializer or create a client specific one.
        # Since AdminSubmissionListSerializer works well for a flat list, we'll use it
        # but we need to import it. Or just build a simple response.
        submissions = CityTestSubmission.objects.filter(client=client).select_related('test', 'test__category').order_by('-submitted_at')
        
        # Build simple dict for client
        data = []
        for sub in submissions:
            data.append({
                "id": sub.id,
                "test_id": sub.test_id,
                "category_id": sub.test.category_id if sub.test else None,
                "title": sub.test.title if sub.test else None,
                "notes": sub.notes,
                "question_for_liv_team": sub.question_for_liv_team,
                "links": sub.links,
                "submitted_at": sub.submitted_at
            })
            
        return Response({"submissions": data}, status=status.HTTP_200_OK)


# =============================================================================
# SOLO DISCOVERY MICRO-TESTS — Client View
# =============================================================================

class SoloMicroTestListView(APIView):
    """
    GET /api/app/solo-micro-tests

    Returns all solo micro-test groups with their tasks.

    SRP — Only serves the solo micro-test list.
    ISP — Returns only what the PWA needs: group name + item id/title/description.
          Admin metadata (timestamps, order) is excluded from the client response.
    OCP — The title/description envelope values are defined in the response dict.
          Changing the title = change one line here.

    "Without OCP, if the title 'Solo Discovery Micro-Tests' was hardcoded in
     6 views, a rebrand would require 6 changes. With OCP, it's one location."

    DIP — Depends on SoloMicroTestGroupSerializer, not raw model dicts.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        groups = SoloMicroTestGroup.objects.prefetch_related('items').order_by('order')

        serializer = SoloMicroTestGroupSerializer(groups, many=True)

        return Response(
            {
                "title": "Solo Discovery Micro-Tests",
                "description": (
                    "Small, meaningful experiments to help you discover "
                    "how the city works in practice."
                ),
                "groups": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
