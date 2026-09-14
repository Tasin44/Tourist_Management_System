"""
clients/serializers.py

SOLID PRINCIPLE APPLIED:
- Single Responsibility Principle (SRP): Each serializer handles validation and
  serialization for exactly ONE model. No serializer touches multiple domain
  concerns.
  "Without SRP, one mega-serializer would validate clients, trips, and bookings
   all at once — making it impossible to reuse or independently test each."

- Open/Closed Principle (OCP): Multi-select fields use a reusable
  MultiSelectField approach so adding new choices requires no serializer changes.
  "Without OCP, adding a new lifestyle option would require editing validate_*
   methods in multiple places."

OOP APPLIED:
- Nested serializers (ClientDashboardSerializer) compose smaller serializers
  instead of duplicating fields — a use of composition over inheritance.
"""

from rest_framework import serializers
from django.contrib.auth.models import User

from .models import (
    Client,
    Trip,
    AnonymousBooking,
    FinancialProfile,
    LifestyleAlignment,
)


# =============================================================================
# Reusable Multi-Select Field
# OCP: Adding new multi-select fields to any serializer just reuses this field.
# SRP: All comma-join/split logic lives here, not scattered across serializers.
# =============================================================================

class CommaSeparatedField(serializers.Field):
    """
    Custom field for multi-select values stored as comma-separated strings.

    OOP — Inherits from serializers.Field, overriding to_internal_value
          (list -> string) and to_representation (string -> list).

    SRP — This field has ONE job: convert between list <-> comma string.

    "Without this, every serializer would repeat split/join logic, and a bug
     in that logic would require fixes in every serializer file."
    """

    def to_representation(self, value: str):
        """Convert comma string to list for API output."""
        if not value:
            return []
        return [v.strip() for v in value.split(',') if v.strip()]

    def to_internal_value(self, data):
        """Convert list or comma string to stored comma string."""
        if isinstance(data, list):
            return ','.join(str(item).strip() for item in data)
        if isinstance(data, str):
            return data.strip()
        raise serializers.ValidationError("Expected a list or comma-separated string.")


# =============================================================================
# Client Serializers
# =============================================================================

class ClientCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new Client.

    SRP — Handles ONLY create validation. Read serializer is separate.
    "Without SRP, mixing create and read logic in one serializer would
     expose write-only fields (like notes) in read responses, or require
     complex conditional logic — a maintenance nightmare."
    """

    class Meta:
        model = Client
        fields = [
            'full_name',
            'email',
            'phone',
            'target_destination',
            'visa',
            'target_arrival_timeline',
            'household_size',
            'lead_advisor_name',
            'notes',
        ]

    def validate_email(self, value: str) -> str:
        """
        SRP: Email uniqueness check lives here, not in the view.
        OCP: Adding extra email validation rules means extending this method.
        """
        if Client.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A client with this email already exists."
            )
        return value.lower()


class ClientReadSerializer(serializers.ModelSerializer):
    """
    Serializer for reading/listing Client records.

    SRP — Read-only representation. Create fields (notes, lead_advisor) are
          included but read-only here.
    """

    class Meta:
        model = Client
        fields = [
            'id',
            'full_name',
            'email',
            'phone',
            'target_destination',
            'visa',
            'target_arrival_timeline',
            'household_size',
            'lead_advisor_name',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


# =============================================================================
# Trip Serializers
# =============================================================================

class TripCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a Trip for a specific client.

    SRP — Only handles Trip creation validation.
    Note: client_id is injected from the URL (client_id kwarg), not the body.
    "Without SRP, validating client existence in a generic Trip serializer would
     leak URL routing logic into the serializer layer."
    """

    class Meta:
        model = Trip
        fields = [
            'city',
            'timeline',
            'guide_name',
            'property_views',
        ]


class TripReadSerializer(serializers.ModelSerializer):
    """
    Serializer for reading Trip details, including nested client info.

    OOP — Composition: uses ClientReadSerializer nested inside for client detail.
    SRP — Read-only. Mutation uses TripCreateSerializer.
    """
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    email = serializers.EmailField(source='client.email', read_only=True)
    visa = serializers.CharField(source='client.visa', read_only=True)
    client_id = serializers.IntegerField(source='client.id', read_only=True)
    tour_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id',
            'tour_id',
            'client_id',
            'client_name',
            'email',
            'visa',
            'city',
            'timeline',
            'guide_name',
            'property_views',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class TripUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for partial/full update of a Trip (admin only).

    SRP — Handles ONLY trip mutation for admin use.
    OCP — New updatable fields are added here without touching read or create serializers.
    """

    class Meta:
        model = Trip
        fields = [
            'city',
            'timeline',
            'guide_name',
            'property_views',
        ]
        extra_kwargs = {field: {'required': False} for field in fields}


# =============================================================================
# Anonymous Booking Serializer
# =============================================================================

class AnonymousBookingSerializer(serializers.ModelSerializer):
    """
    Serializer for anonymous booking submissions.

    SRP — Only handles AnonymousBooking. No client creation happens here.
    OCP — New booking fields are added by extending this serializer.

    "Without SRP, if anonymous booking created a Client automatically,
     we'd couple two different business flows together — making it hard
     to change one without breaking the other."
    """

    # Multi-select field: accepts list from frontend, stores as comma string
    considering_places_type = CommaSeparatedField()

    class Meta:
        model = AnonymousBooking
        fields = [
            'full_name',
            'email',
            'phone_number',
            'relocation_process_type',
            'considering_places_type',
            'scouting_people_type',
        ]

    def validate_relocation_process_type(self, value: str) -> str:
        """
        OCP — Validation rule lives here; adding new rules = extend this method.
        """
        valid_keys = [k for k, _ in AnonymousBooking.RELOCATION_PROCESS_CHOICES]
        if value not in valid_keys:
            raise serializers.ValidationError(
                f"Invalid choice. Valid options: {valid_keys}"
            )
        return value


class AnonymousBookingReadSerializer(serializers.ModelSerializer):
    """
    Read serializer for admin listing of anonymous bookings.
    SRP — Separate from write serializer; read-only.
    """
    considering_places_type = CommaSeparatedField()

    class Meta:
        model = AnonymousBooking
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'relocation_process_type',
            'considering_places_type',
            'scouting_people_type',
            'created_at',
        ]
        read_only_fields = fields


# =============================================================================
# Financial Profile Serializer
# =============================================================================

class FinancialProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/reading a client's FinancialProfile.

    SRP — All financial field validation lives here.
    OCP — New financial fields are added by extending this serializer.
    DIP — CommaSeparatedField handles multi-select storage details; this
          serializer doesn't need to know HOW they're stored.

    "Without DIP, every multi-select field would repeat the same list->string
     conversion code, and a change to storage format would break every serializer."
    """

    motivating_factors        = CommaSeparatedField(required=False)
    willing_tradeoffs         = CommaSeparatedField(required=False)
    practical_constraints     = CommaSeparatedField(required=False)
    financial_excitement_factors = CommaSeparatedField(required=False)

    class Meta:
        model = FinancialProfile
        fields = [
            'id',
            'motivating_factors',
            'financial_note',
            'comfortable_housing_budget',
            'stretched_housing_budget',
            'monthly_living_budget_target',
            'share_your_opinion',
            'general_monthly_living_budget_target',
            'specific_codes_worried_about',
            'financial_expectation',
            'income_route',
            'income_route_note',
            'willing_tradeoffs',
            'unwilling_tradeoffs_note',
            'practical_constraints',
            'practical_constraints_note',
            'specific_cost_worries',
            'financial_excitement_factors',
            'financial_excitement_note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_financial_expectation(self, value: str) -> str:
        """OCP — Validation is extensible without touching other methods."""
        if value:
            valid = [k for k, _ in FinancialProfile.FINANCIAL_EXPECTATION_CHOICES]
            if value not in valid:
                raise serializers.ValidationError(
                    f"Invalid choice. Valid: {valid}"
                )
        return value

    def validate_income_route(self, value: str) -> str:
        if value:
            valid = [k for k, _ in FinancialProfile.INCOME_ROUTE_CHOICES]
            if value not in valid:
                raise serializers.ValidationError(
                    f"Invalid choice. Valid: {valid}"
                )
        return value


# =============================================================================
# Lifestyle Alignment Serializer
# =============================================================================

class LifestyleAlignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/reading a client's LifestyleAlignment.

    SRP — All lifestyle validation lives here; no financial or trip logic.
    ISP — Clients only receive lifestyle data when this specific endpoint is
          called — they're not burdened with unrelated financial fields.

    "Without ISP, if we returned all client data from one endpoint, a mobile
     app fetching only lifestyle info would receive kilobytes of irrelevant
     financial data on every request."
    """

    daily_life_desires        = CommaSeparatedField(required=False)
    environmental_pull_factors = CommaSeparatedField(required=False)
    internal_pull_factors     = CommaSeparatedField(required=False)

    class Meta:
        model = LifestyleAlignment
        fields = [
            'id',
            'daily_life_desires',
            'good_weekday',
            'good_weekend',
            'routines_note',
            'current_day_description',
            'environmental_pull_factors',
            'environmental_pull_note',
            'internal_pull_factors',
            'internal_pull_note',
            'shadow_fear',
            'anchor_aspiration',
            'success_picture',
            'desired_emotions',
            'glad_i_did_this_moment',
            'routines_real_life',
            'day_looked_like',
            'anything_to_add',
            'imagine_life_working',
            'emotions_hope_to_feel',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# =============================================================================
# Client Dashboard Serializer (nested read-only view for the client portal)
# OOP: Composition — assembles multiple serializers into one coherent response.
# =============================================================================

class ClientDashboardSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the client dashboard — shows the client their
    target city, advisor (guide), and upcoming trips.

    OOP — Composition: nests TripReadSerializer without duplicating fields.
    SRP — This serializer exists only for the dashboard view; it is not reused
          for admin listing.

    "Without composition, we'd duplicate all trip fields here manually —
     meaning a change to trip structure requires editing two places."
    """

    trips = TripReadSerializer(many=True, read_only=True)
    target_city = serializers.CharField(source='target_destination', read_only=True)
    advisor = serializers.CharField(source='lead_advisor_name', read_only=True)

    class Meta:
        model = Client
        fields = [
            'id',
            'full_name',
            'email',
            'target_city',
            'visa',
            'target_arrival_timeline',
            'advisor',
            'trips',
        ]
        read_only_fields = fields
