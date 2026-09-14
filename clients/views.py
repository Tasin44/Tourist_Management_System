"""
clients/views.py

SOLID PRINCIPLE APPLIED:
- Single Responsibility Principle (SRP): Each APIView/ViewSet handles exactly
  one resource + one HTTP method group. No view handles multiple concerns.
  "Without SRP, a single 'ClientView' that creates clients, sends emails,
   lists trips, and handles bookings would be impossible to test in isolation."

- Open/Closed Principle (OCP): Views are open for extension (new endpoints)
  but closed for modification — new endpoints get new view classes.
  "Without OCP, adding upcoming-trips filtering would require editing the
   existing trip list view, risking breakage of the existing list behavior."

- Dependency Inversion Principle (DIP): Views depend on the ClientCreationService
  abstraction, not directly on User creation or send_mail calls.
  "Without DIP, testing the create_client view would require a live SMTP server."

OOP APPLIED:
- Views inherit from DRF's APIView/GenericAPIView so common HTTP handling
  (auth, serializer, response) is reused via inheritance.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Client, Trip, AnonymousBooking, FinancialProfile, LifestyleAlignment
from .serializers import (
    ClientCreateSerializer,
    ClientReadSerializer,
    ClientDashboardSerializer,
    TripCreateSerializer,
    TripReadSerializer,
    TripUpdateSerializer,
    AnonymousBookingSerializer,
    AnonymousBookingReadSerializer,
    FinancialProfileSerializer,
    LifestyleAlignmentSerializer,
)
from .services import ClientCreationService
from .permissions import IsAdminUser, IsAdminOrClientOwner

from livable.models import CityTestSubmission, DailySchedule
from livable.serializers import AdminSubmissionListSerializer, AdminDailyScheduleReadSerializer


# =============================================================================
# CLIENT ENDPOINTS
# =============================================================================

class CreateClientView(APIView):
    """
    POST /api/clients/create/

    Creates a new client, a portal login user, and sends the welcome email.

    SRP — This view's only job is to accept POST, delegate to the service,
          and return the response. It doesn't know HOW the user is created
          or HOW the email is sent.

    DIP — Depends on ClientCreationService (injected), not concrete email/user logic.

    "Without DIP, if send_mail raised an exception during a test, the test
     would fail even though the business logic was correct."
    """

    permission_classes = [IsAdminUser]

    # DIP: service is a class attribute so it can be overridden in tests
    client_creation_service_class = ClientCreationService

    def post(self, request):
        serializer = ClientCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # DIP: instantiate service here — can be mocked in tests
        service = self.client_creation_service_class()
        client = service.create(validated_data=serializer.validated_data)

        return Response(
            ClientReadSerializer(client).data,
            status=status.HTTP_201_CREATED,
        )


class ListClientsView(ListAPIView):
    """
    GET /api/clients/

    Lists all clients. Admin only.

    SRP — Only lists clients; does not handle create or detail.
    OCP — Filtering/ordering can be added via DRF filter backends without
          changing this class.
    """

    permission_classes = [IsAdminUser]
    serializer_class = ClientReadSerializer
    queryset = Client.objects.select_related('user').order_by('-created_at')


class ClientTargetDestinationsView(APIView):
    """
    GET /api/clients/target_destination/

    Returns a distinct list of all target destinations from all clients.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        destinations = (
            Client.objects
            .exclude(target_destination='')
            .exclude(target_destination__isnull=True)
            .values_list('target_destination', flat=True)
            .distinct()
            .order_by('target_destination')
        )
        return Response({
            "target_destinations": list(destinations)
        }, status=status.HTTP_200_OK)


# =============================================================================
# TRIP ENDPOINTS
# =============================================================================

class CreateTripView(APIView):
    """
    POST /api/clients/{client_id}/trips/

    Creates a new scouting trip for a specific client.

    SRP — Only handles trip creation.
    OCP — Adding fields to a trip requires only updating TripCreateSerializer.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, client_id):
        # Lookup client — 404 if not found
        client = self._get_client_or_404(client_id)
        if isinstance(client, Response):
            return client

        serializer = TripCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        trip = Trip.objects.create(client=client, **serializer.validated_data)
        return Response(
            TripReadSerializer(trip).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _get_client_or_404(client_id):
        """
        OOP — Private helper encapsulates lookup + error response.
        SRP — Lookup logic doesn't pollute the post() method.
        """
        try:
            return Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response(
                {"detail": f"Client {client_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


class ClientTodaysView(ListAPIView):
    """
    GET /api/clients/{client_id}/todays/
    
    Lists all DailySchedules for a specific client.
    Accessible by Admin or the specific Client.
    """
    permission_classes = [IsAdminOrClientOwner]
    serializer_class = AdminDailyScheduleReadSerializer

    def get_queryset(self):
        return (
            DailySchedule.objects
            .filter(client_id=self.kwargs['client_id'])
            .prefetch_related('items')
            .order_by('-date')
        )


class ClientCityTestsView(ListAPIView):
    """
    GET /api/clients/{client_id}/city-tests/
    
    Lists all city tests submitted by a specific client.
    Accessible by Admin or the specific Client.
    """
    permission_classes = [IsAdminOrClientOwner]
    serializer_class = AdminSubmissionListSerializer

    def get_queryset(self):
        return (
            CityTestSubmission.objects
            .filter(client_id=self.kwargs['client_id'])
            .select_related('test', 'test__category')
            .order_by('-submitted_at')
        )


class ClientTripDetailView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/clients/{client_id}/trips/{trip_id}/   — client owner OR admin
    PUT    /api/clients/{client_id}/trips/{trip_id}/   — admin only
    PATCH  /api/clients/{client_id}/trips/{trip_id}/   — admin only
    DELETE /api/clients/{client_id}/trips/{trip_id}/   — admin only

    OCP — Uses RetrieveUpdateDestroyAPIView; adding HEAD/OPTIONS is automatic.
    SRP — Only manages a single trip's detail/edit/delete lifecycle.
    """

    # IsAdminOrClientOwner handles: GET for owner, all methods for admin
    permission_classes = [IsAdminOrClientOwner]

    def get_queryset(self):
        """
        OOP — get_queryset() scopes trips to the client in the URL.
        This prevents client A from accessing client B's trips via URL manipulation.
        """
        return Trip.objects.filter(client_id=self.kwargs['client_id'])

    def get_serializer_class(self):
        """
        OCP — Serializer selection is open for extension: read vs write serializers
              are selected by method without modifying either serializer class.
        """
        if self.request.method in ('PUT', 'PATCH'):
            return TripUpdateSerializer
        return TripReadSerializer

    def get_object(self):
        """
        OOP — Overrides get_object to ensure ownership check via has_object_permission.
        """
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        """Admin-only guard for mutations."""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only admins can edit trips."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Admin-only guard for deletion."""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only admins can delete trips."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class ListAllTripsView(ListAPIView):
    """
    GET /api/trips/

    Lists all trips across all clients. Admin only.

    SRP — Only lists trips.
    OCP — Ordering/filtering can be extended via filter backends.
    """

    permission_classes = [IsAdminUser]
    serializer_class = TripReadSerializer

    def get_queryset(self):
        return (
            Trip.objects
            .select_related('client')
            .order_by('-created_at')
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        from .models import Client
        total_clients = Client.objects.count()
        total_trips = queryset.count()
        
        return Response({
            "total_clients": total_clients,
            "total_trips": total_trips,
            "trips": serializer.data
        })


class UpcomingTripsView(ListAPIView):
    """
    GET /api/trips/upcoming/

    Returns all trips (upcoming concept — filterable by timeline keyword).
    Admin only.

    SRP — Separate from past/all trips to keep each concern isolated.
    OCP — The definition of 'upcoming' can be changed here without touching
          ListAllTripsView.

    "Without OCP, adding upcoming filter logic to the existing list view would
     require conditional branching — making both behaviors harder to test."
    """

    permission_classes = [IsAdminUser]
    serializer_class = TripReadSerializer

    def get_queryset(self):
        """
        OOP — Encapsulates the upcoming-trips query. Currently returns all trips;
        real implementation would filter by parsed timeline date > today.
        """
        return (
            Trip.objects
            .select_related('client')
            .order_by('created_at')  # ascending for upcoming
        )


class RecentTripsView(ListAPIView):
    """
    GET /api/trips/recent/

    Returns the most recent trips. Admin only.

    SRP — Separate from UpcomingTripsView so each has a single, clear purpose.
    """

    permission_classes = [IsAdminUser]
    serializer_class = TripReadSerializer

    def get_queryset(self):
        return (
            Trip.objects
            .select_related('client')
            .order_by('-created_at')[:20]  # 20 most recent
        )


# =============================================================================
# CLIENT DASHBOARD (client sees their own data)
# =============================================================================

class ClientDashboardView(APIView):
    """
    GET /api/me/dashboard/

    Returns the authenticated client's dashboard:
    target city, advisor (guide name), and their trips.

    SRP — Only serves the client dashboard. Admin listing is a separate view.
    ISP — Client gets only their own data; admin endpoints are separate.

    "Without ISP, if we used one view for both admin listing and client dashboard,
     the client would accidentally receive other clients' data on auth mistakes."
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            client = request.user.client_profile
        except Client.DoesNotExist:
            return Response(
                {"detail": "No client profile found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ClientDashboardSerializer(client)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClientMyTripsView(APIView):
    """
    GET /api/me/trips/

    Returns a list of all trips belonging to the authenticated client,
    plus a total count.

    SRP — Only serves the client's own trip list.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            client = request.user.client_profile
        except Client.DoesNotExist:
            return Response(
                {"detail": "No client profile found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        trips = Trip.objects.filter(client=client).order_by('timeline')
        serializer = TripReadSerializer(trips, many=True)
        
        return Response({
            "total": trips.count(),
            "trips": serializer.data
        }, status=status.HTTP_200_OK)


# =============================================================================
# ANONYMOUS BOOKING
# =============================================================================

class AnonymousBookingCreateView(APIView):
    """
    POST /api/anonymous/book/

    Allows any user (no auth required) to submit a booking inquiry.

    SRP — Only handles anonymous booking submission.
    OCP — Adding new booking fields requires only updating the serializer.
    """

    permission_classes = [AllowAny]  # No authentication required

    def post(self, request):
        serializer = AnonymousBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        booking = serializer.save()
        return Response(
            AnonymousBookingReadSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )


class AnonymousBookingListView(ListAPIView):
    """
    GET /api/anonymous/book/

    Lists all anonymous bookings. Admin only.

    SRP — Only lists bookings; create is handled by AnonymousBookingCreateView.
    """

    permission_classes = [IsAdminUser]
    serializer_class = AnonymousBookingReadSerializer
    queryset = AnonymousBooking.objects.order_by('-created_at')


# =============================================================================
# FINANCIAL PROFILE
# =============================================================================

class CreateFinancialProfileView(APIView):
    """
    POST /api/clients/{client_id}/financial-profile/

    Creates (or updates) the financial profile for a client.

    SRP — Only handles financial profile persistence.
    OCP — New financial fields are added to the serializer, not here.
    DIP — Depends on FinancialProfileSerializer abstraction, not raw model.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, client_id):
        client = self._get_accessible_client(request, client_id)
        if isinstance(client, Response):
            return client

        # Use get_or_create so POST is idempotent
        profile, _ = FinancialProfile.objects.get_or_create(client=client)
        serializer = FinancialProfileSerializer(profile, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def _get_accessible_client(request, client_id):
        """
        SRP — Access-control lookup isolated in one private helper.
        OCP — Changing access rules means editing only this helper.
        """
        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response(
                {"detail": "Client not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Admin can access any client; client can only access themselves
        if not request.user.is_staff and client.user != request.user:
            return Response(
                {"detail": "Access denied."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return client


# =============================================================================
# LIFESTYLE ALIGNMENT
# =============================================================================

class CreateLifestyleAlignmentView(APIView):
    """
    POST /api/clients/{client_id}/lifestyle-alignment/

    Creates (or updates) the lifestyle alignment for a client.

    SRP — Only handles lifestyle alignment data.
    ISP — Separate from financial profile; clients aren't forced to submit
          financial data just to update their lifestyle profile.

    "Without ISP, combining lifestyle and financial into one endpoint would
     require clients to re-submit financial data every time they update
     their lifestyle preferences."
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, client_id):
        client = CreateFinancialProfileView._get_accessible_client(request, client_id)
        if isinstance(client, Response):
            return client

        alignment, _ = LifestyleAlignment.objects.get_or_create(client=client)
        serializer = LifestyleAlignmentSerializer(alignment, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
