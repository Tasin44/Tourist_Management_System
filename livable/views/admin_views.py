"""
livable/views/admin_views.py

All admin-facing API views for the livable app.

SOLID PRINCIPLES APPLIED:
──────────────────────────────────────────────────────────────────────────────
S — Single Responsibility:
    Each view class handles exactly one endpoint/action.
    AdminTodayCreateView   → POST  /admin/today/{user_id}
    AdminScheduleItemView  → PUT/DELETE /admin/today/item/{item_id}
    AdminCityTestListCreateView → POST /admin/city-tests
    AdminCityTestDetailView     → PUT/DELETE /admin/city-tests/{test_id}
    AdminSubmissionsView        → GET /admin/city-tests/submissions

    "Without SRP, one 'AdminView' class handling schedule + city-tests + submissions
     would grow to 500+ lines — untestable, unreadable, un-maintainable."

O — Open/Closed:
    Pagination for submissions is handled via a dedicated helper — new pagination
    strategies (cursor, keyset) are added by extending the helper, not editing views.

    "Without OCP, adding cursor pagination to submissions would require editing
     AdminSubmissionsView directly, risking breaking offset pagination."

D — Dependency Inversion:
    Views depend on serializer abstractions. Changing the serializer (e.g.,
    adding a field) requires zero changes to the view.

    "Without DIP, if views directly built response dicts from model fields,
     every field addition would require editing both the model AND the view."

OOP APPLIED:
    • _get_client_or_404 is a reusable static helper — DRY, testable.
    • _paginate_queryset encapsulates offset pagination — reusable across views.
    • All views inherit APIView, gaining auth/permission enforcement via inheritance.
"""

from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from clients.models import Client
from clients.permissions import IsAdminUser
from livable.models import (
    DailySchedule,
    ScheduleItem,
    CityTest,
    CityTestCategory,
    CityTestSubmission,
)
from livable.serializers import (
    AdminDailyScheduleWriteSerializer,
    AdminScheduleItemWriteSerializer,
    AdminScheduleItemReadSerializer,
    AdminCityTestWriteSerializer,
    AdminCityTestReadSerializer,
    AdminSubmissionListSerializer,
)


# =============================================================================
# Shared Utility Helpers
# SRP: Helpers are static methods — their only job is the named task.
# DIP: Views call these helpers rather than embedding the logic themselves.
# =============================================================================

def get_client_or_404(client_id) -> tuple:
    """
    SRP — Fetches a Client by PK and returns (client, error_response).
    DIP — Views depend on this helper, not on Client.objects.get directly.

    "Without this helper, every admin view would repeat:
       try: client = Client.objects.get(pk=...) except: return 404
     — that's N copies of the same logic, all needing fixes if the 404
     message ever changes."
    """
    try:
        return Client.objects.get(pk=client_id), None
    except Client.DoesNotExist:
        err = Response(
            {"detail": f"Client {client_id} not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
        return None, err


def paginate_queryset(queryset, request, default_limit: int = 20):
    """
    OCP — Centralised offset pagination. New pagination strategies are added
    by creating new helper functions, not by editing this one.

    SRP — Only computes page/limit slicing and total count.

    "Without OCP, if we later want cursor pagination, we'd add a new function
     rather than modifying this one — protecting existing callers."
    """
    try:
        page  = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', default_limit))
    except ValueError:
        page, limit = 1, default_limit

    page  = max(page, 1)
    limit = min(max(limit, 1), 100)  # cap at 100

    offset = (page - 1) * limit
    total  = queryset.count()
    return queryset[offset: offset + limit], total, page, limit


# =============================================================================
# SCHEDULE / TODAY — Admin Views
# =============================================================================

class AdminTodayCreateView(APIView):
    """
    POST /api/admin/today/{user_id}

    Admin creates or replaces a full day's schedule for a client.
    Uses a database transaction so partial failures leave no orphan records.

    SRP — Only handles schedule creation/replacement for a given client+date.
    OCP — Adding schedule metadata (e.g., city) = add to serializer only.

    "Without SRP, if this view also handled item-level updates (PUT/item),
     a bug in item update logic would block schedule creation deployment."

    DIP — Depends on AdminDailyScheduleWriteSerializer, not raw dicts.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        client, err = get_client_or_404(user_id)
        if err:
            return err

        serializer = AdminDailyScheduleWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        items_data = data.pop('items', [])

        # OOP: transaction.atomic ensures the create+items is all-or-nothing
        with transaction.atomic():
            # get_or_create: idempotent — POST can be called again to rebuild a day
            schedule, _ = DailySchedule.objects.get_or_create(
                client=client,
                date=data['date'],
            )
            # Replace existing items (admin is re-posting the full day)
            schedule.items.all().delete()

            # Bulk-create items for performance
            # OCP: adding a new item field = update the serializer; this loop doesn't change
            items = [
                ScheduleItem(schedule=schedule, **item_data)
                for item_data in items_data
            ]
            ScheduleItem.objects.bulk_create(items)

        # Re-fetch with prefetch for serialization
        schedule = (
            DailySchedule.objects
            .prefetch_related('items')
            .get(pk=schedule.pk)
        )

        return Response(
            {
                "success": True,
                "date": str(schedule.date),
                "client_id": client.pk,
                "items_count": schedule.items.count(),
                "items": AdminScheduleItemReadSerializer(
                    schedule.items.all(), many=True
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminScheduleItemView(APIView):
    """
    PUT    /api/admin/today/item/{item_id}   → Update a single schedule item
    DELETE /api/admin/today/item/{item_id}   → Delete a single schedule item

    SRP — Only handles single-item mutation. Full-day creation is in AdminTodayCreateView.
    OCP — New HTTP methods (PATCH) are added by adding a `patch` method; no existing
          methods need modification.

    "Without SRP, combining full-day creation and single-item editing in one view
     would mean a bug in DELETE could accidentally break the POST creation flow."
    """

    permission_classes = [IsAdminUser]

    def _get_item_or_404(self, item_id):
        """
        OOP — Private helper encapsulates item lookup + 404 response.
        SRP — Lookup concern is isolated; put/delete methods stay clean.
        """
        try:
            return ScheduleItem.objects.get(pk=item_id), None
        except ScheduleItem.DoesNotExist:
            err = Response(
                {"detail": f"Schedule item {item_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
            return None, err

    def put(self, request, item_id):
        """Admin updates a single schedule item (full or partial)."""
        item, err = self._get_item_or_404(item_id)
        if err:
            return err

        # partial=True so admin can send only the fields they want to change
        serializer = AdminScheduleItemWriteSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            AdminScheduleItemReadSerializer(item).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, item_id):
        """Admin deletes a single schedule item."""
        item, err = self._get_item_or_404(item_id)
        if err:
            return err

        item.delete()
        return Response(
            {"success": True, "item_id": str(item_id), "message": "Schedule item deleted."},
            status=status.HTTP_200_OK,
        )


# =============================================================================
# CITY TESTS — Admin Views
# =============================================================================

class AdminCityTestListCreateView(APIView):
    """
    POST /api/admin/city-tests/

    Admin creates a new CityTest.

    SRP — Only handles creation. Update/delete are in AdminCityTestDetailView.
    OCP — New city test fields are added to AdminCityTestWriteSerializer only.

    "Without OCP, adding a 'video_link' field to city tests would require editing
     this view's POST body parsing AND the update view AND the read serializer —
     a cascade of changes for one new field."
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminCityTestWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        test = serializer.save()

        return Response(
            {
                "success": True,
                "test": AdminCityTestReadSerializer(test).data,
                "message": "City Test created successfully",
            },
            status=status.HTTP_201_CREATED,
        )


class AdminCityTestDetailView(APIView):
    """
    PUT    /api/admin/city-tests/{test_id}   → Update an existing CityTest
    DELETE /api/admin/city-tests/{test_id}   → Delete a CityTest

    SRP — Only handles single-test mutation.
    OCP — Adding a PATCH method = add a `patch` method here; no other change.

    "Without OCP, if we added a PATCH method that partially updates by merging
     JSONFields, that logic would live only in this method — the PUT method
     and its tests are untouched."
    """

    permission_classes = [IsAdminUser]

    def _get_test_or_404(self, test_id):
        """OOP — Private lookup helper. SRP — lookup isolated from HTTP methods."""
        try:
            return CityTest.objects.get(pk=test_id), None
        except CityTest.DoesNotExist:
            err = Response(
                {"detail": f"City Test '{test_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
            return None, err

    def put(self, request, test_id):
        test, err = self._get_test_or_404(test_id)
        if err:
            return err

        # partial=True: admin sends only changed fields
        serializer = AdminCityTestWriteSerializer(test, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        test = serializer.save()
        return Response(
            {
                "success": True,
                "test": AdminCityTestReadSerializer(test).data,
                "message": "City Test updated successfully",
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, test_id):
        test, err = self._get_test_or_404(test_id)
        if err:
            return err

        test.delete()
        return Response(
            {
                "success": True,
                "test_id": test_id,
                "message": "City Test deleted successfully",
            },
            status=status.HTTP_200_OK,
        )


class AdminSubmissionsView(APIView):
    """
    GET /api/admin/city-tests/submissions

    Lists all client test submissions with optional filters.

    SRP — Only handles listing/filtering of submissions.
    OCP — New filter parameters (e.g., ?date_from=) are added without
          changing existing filter logic.

    "Without OCP, adding a ?date_from filter would require editing the
     existing if-blocks in this view, risking breaking existing filters."

    DIP — Depends on AdminSubmissionListSerializer abstraction.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            CityTestSubmission.objects
            .select_related('client', 'test', 'test__category')
            .order_by('-submitted_at')
        )

        # OCP: each filter is an independent, additive narrowing — easy to extend
        category_id = request.query_params.get('category_id')
        test_id     = request.query_params.get('test_id')
        user_id     = request.query_params.get('user_id')

        if category_id:
            qs = qs.filter(test__category_id=category_id)
        if test_id:
            qs = qs.filter(test_id=test_id)
        if user_id:
            qs = qs.filter(client_id=user_id)

        page_qs, total, page, limit = paginate_queryset(qs, request)

        return Response(
            {
                "total": total,
                "page": page,
                "limit": limit,
                "submissions": AdminSubmissionListSerializer(page_qs, many=True).data,
            },
            status=status.HTTP_200_OK,
        )
