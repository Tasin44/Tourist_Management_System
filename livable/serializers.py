"""
livable/serializers.py

SOLID PRINCIPLES APPLIED:
──────────────────────────────────────────────────────────────────────────────
S — Single Responsibility:
    Each serializer class handles exactly one model's read OR write concern.
    Admin write serializers are separate from client read serializers.
    "Without SRP, a serializer that handles both admin creation AND client-facing
     display would expose admin-only fields (host_name, what_to_bring) to every
     client reading the item list."

O — Open/Closed:
    New fields are added by extending the fields list or adding a new serializer
    subclass — never by editing the existing serializer's core logic.
    "Without OCP, adding a 'reminder' field to ScheduleItem would require editing
     the AdminScheduleItemSerializer, ClientScheduleItemSerializer, and every
     view that manually plucks fields — a ripple of changes."

I — Interface Segregation:
    Client-facing serializers return only what the client needs.
    Admin serializers include all management fields.
    "Without ISP, returning the full DailySchedule serializer to clients would
     expose the admin's internal ordering, host notes, and other management data
     to the PWA."

D — Dependency Inversion:
    Serializers depend on model fields and DRF abstractions, not on raw SQL
    or direct model method calls — they are testable in complete isolation.

OOP APPLIED:
    • Nested serializers (ScheduleItemDetailSerializer inside ClientScheduleItemSerializer)
      use composition rather than duplication.
    • get_* methods on SerializerMethodField encapsulate computed presentation logic.
"""

from rest_framework import serializers
from django.utils import timezone

from .models import (
    DailySchedule,
    ScheduleItem,
    CityTestCategory,
    CityTest,
    CityTestSubmission,
    SoloMicroTestGroup,
    SoloMicroTest,
)


# =============================================================================
# SECTION 1: SCHEDULE / TODAY SERIALIZERS
# =============================================================================

# ── Admin write serializers ───────────────────────────────────────────────────

class AdminScheduleItemWriteSerializer(serializers.ModelSerializer):
    """
    Used by admin to CREATE or UPDATE a single ScheduleItem.

    SRP — Write concern only; no computed/presentation fields here.
    OCP — New item fields are added to this list without touching the read serializer.

    "Without SRP, if we combined admin-write and client-read in one serializer,
     every client GET /today would require the serializer to silently drop
     admin-only fields — error-prone and hard to audit."
    """

    class Meta:
        model = ScheduleItem
        fields = [
            'start_time',
            'end_time',
            'title',
            'item_type',
            'short_description',
            'description',
            'host_name',
            'meeting_point',
            'what_to_bring',
            'google_maps_link',
            'restaurant_link',
            'phone',
            'website',
            'reminder',
            'order',
        ]
        extra_kwargs = {
            # OCP: marking non-required fields here, not in the view
            field: {'required': False}
            for field in [
                'short_description', 'description', 'host_name',
                'meeting_point', 'what_to_bring', 'google_maps_link',
                'restaurant_link', 'phone', 'website', 'reminder', 'order',
            ]
        }


class AdminDailyScheduleWriteSerializer(serializers.Serializer):
    """
    Used by admin to POST an entire day's schedule for a client.

    SRP — Handles only the admin creation request shape:
          { date: ..., items: [...] }

    OCP — The items list delegates to AdminScheduleItemWriteSerializer;
          changing item fields doesn't require touching this class.

    "Without OCP, if we embedded item field validation here manually,
     every new item field would require editing two serializers."
    """

    date  = serializers.DateField()
    items = AdminScheduleItemWriteSerializer(many=True, required=False, default=list)


# ── Client read serializers ───────────────────────────────────────────────────

class ScheduleItemDetailSerializer(serializers.ModelSerializer):
    """
    The 'details' sub-object shown when a client expands a schedule item.

    ISP — Only exposes the detail fields the client needs.
    SRP — This class has one job: serialize the expanded detail block.

    "Without ISP, returning all ScheduleItem fields directly would expose
     admin-only fields like 'order' and internal UUIDs to the PWA."
    """

    class Meta:
        model = ScheduleItem
        fields = [
            'description',
            'host_name',
            'meeting_point',
            'what_to_bring',
            'google_maps_link',
            'restaurant_link',
            'phone',
            'website',
            'reminder',
        ]


class ClientScheduleItemSerializer(serializers.ModelSerializer):
    """
    Client-facing representation of a single schedule item.

    OOP — Composes ScheduleItemDetailSerializer for the 'details' sub-object
          (composition over duplication).
    ISP — Returns only what the PWA needs: time, title, type, expandable flag.

    "Without ISP, returning raw ScheduleItem model data would expose
     schedule.id, order, and other internal fields to the client —
     leaking server-side concerns into the client contract."
    """

    type    = serializers.CharField(source='item_type', read_only=True)
    details = ScheduleItemDetailSerializer(source='*', read_only=True)
    is_expandable = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleItem
        fields = [
            'id',
            'start_time',
            'end_time',
            'title',
            'type',
            'short_description',
            'is_expandable',
            'details',
        ]

    def get_is_expandable(self, obj: ScheduleItem) -> bool:
        """
        OOP — Delegates to the model's encapsulated property.
        SRP — Presentation decision lives in model property, not here.
        """
        return obj.is_expandable


class ClientDailyScheduleSerializer(serializers.ModelSerializer):
    """
    Full 'Today' response for the client PWA.

    OOP — Composes ClientScheduleItemSerializer (many=True).
    SRP — Only assembles the client-facing day view; admin views use separate classes.

    The greeting and subtitle are computed via SerializerMethodField
    so they can be personalised without changing the model.

    "Without SRP, if admin and client used the same serializer with 'if is_admin'
     branching inside, a change to the client greeting would risk touching admin
     response logic — risky and untestable in isolation."
    """

    client_name = serializers.CharField(source='client.full_name', read_only=True)
    greeting    = serializers.SerializerMethodField()
    subtitle    = serializers.SerializerMethodField()
    day_number  = serializers.SerializerMethodField()
    items       = ClientScheduleItemSerializer(many=True, read_only=True)

    class Meta:
        model = DailySchedule
        fields = [
            'client_name',
            'greeting',
            'subtitle',
            'day_number',
            'date',
            'items',
        ]

    def get_greeting(self, obj: DailySchedule) -> str:
        """
        OOP — Encapsulates greeting logic.
        OCP — To change the greeting format, only this method changes.

        "Without OCP, if 'Good morning' was hardcoded in the view,
         adding time-based greetings would require editing the view —
         mixing presentation logic with routing logic."
        """
        hour = timezone.localtime(timezone.now()).hour
        if hour < 12:
            prefix = "Good morning"
        elif hour < 18:
            prefix = "Good afternoon"
        else:
            prefix = "Good evening"
        return f"{prefix}, {obj.client.full_name.split()[0]}."

    def get_subtitle(self, obj: DailySchedule) -> str:
        return "Here's what's planned for today."

    def get_day_number(self, obj: DailySchedule) -> int:
        """Delegates to the model's encapsulated day_number property."""
        return obj.day_number


# ── Admin read serializer for schedule ───────────────────────────────────────

class AdminScheduleItemReadSerializer(serializers.ModelSerializer):
    """
    Admin-facing full representation of a ScheduleItem including internal fields.

    SRP — Admin read view; client read uses ClientScheduleItemSerializer.
    """

    type = serializers.CharField(source='item_type', read_only=True)

    class Meta:
        model = ScheduleItem
        fields = '__all__'


# =============================================================================
# SECTION 2: CITY TEST SERIALIZERS
# =============================================================================

# ── Admin write serializers ───────────────────────────────────────────────────

class AdminCityTestWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates/updates a CityTest.

    SRP — Only handles creation/update of test definitions.
    OCP — New fields (e.g., 'video_link') are added to fields list only.

    "Without OCP, adding a 'video_link' field to both the admin write and
     client read serializer as one combined class creates merge-conflict risk
     every time either admin or client requirements change independently."
    """

    class Meta:
        model = CityTest
        fields = [
            'id',
            'category',
            'title',
            'short_description',
            'google_maps_link',
            'external_links',
            'note_prompts',
            'question_prompts',
            'order',
        ]
        extra_kwargs = {
            'id': {'required': True},   # admin must provide the slug id
            'short_description': {'required': False},
            'google_maps_link': {'required': False},
            'external_links': {'required': False},
            'note_prompts': {'required': False},
            'question_prompts': {'required': False},
            'order': {'required': False},
        }


class AdminCityTestReadSerializer(serializers.ModelSerializer):
    """
    Full admin-facing CityTest representation with timestamps.

    SRP — Read-only admin view.
    """

    category_id = serializers.CharField(source='category.id', read_only=True)

    class Meta:
        model = CityTest
        fields = [
            'id',
            'category_id',
            'title',
            'short_description',
            'google_maps_link',
            'external_links',
            'note_prompts',
            'question_prompts',
            'order',
            'created_at',
            'updated_at',
        ]


# ── Client (category listing) serializers ────────────────────────────────────

class ClientCategorySerializer(serializers.ModelSerializer):
    """
    Category listing for the client PWA, including saved_count.

    ISP — Client sees only id, name, description, saved_count.
          Admin management fields (order, timestamps) are excluded.

    SRP — saved_count is computed per-user; this serializer takes the
          authenticated client via context to compute it.

    "Without ISP, returning the full CityTestCategory model to clients
     would expose the admin-facing 'order' field and internal timestamps —
     data the client's PWA has no use for."
    """

    saved_count = serializers.SerializerMethodField()

    class Meta:
        model = CityTestCategory
        fields = ['id', 'name', 'description', 'saved_count']

    def get_saved_count(self, obj: CityTestCategory) -> int:
        """
        OOP — Uses serializer context to access the current client.
        SRP — saved_count computation lives here, not scattered in views.

        "Without SRP, if views computed saved_count and passed it to the serializer
         as extra data, every new category endpoint would duplicate this logic."
        """
        client = self.context.get('client')
        if client is None:
            return 0
        return CityTestSubmission.objects.filter(
            client=client,
            test__category=obj
        ).count()


class ClientTestBriefSerializer(serializers.ModelSerializer):
    """
    Brief test summary for the category-detail listing (id, title, order, is_completed).

    ISP — Client does NOT need prompts or map links at this level.
          Those are fetched per-test via the detail endpoint.

    "Without ISP, returning full CityTest objects in the category listing would
     send kilobytes of prompt text that the client only needs on demand."
    """

    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = CityTest
        fields = ['id', 'title', 'order', 'is_completed']

    def get_is_completed(self, obj: CityTest) -> bool:
        """OOP — Checks submission existence for this client+test pair."""
        client = self.context.get('client')
        if client is None:
            return False
        return CityTestSubmission.objects.filter(client=client, test=obj).exists()


class ClientCategoryDetailSerializer(serializers.ModelSerializer):
    """
    Category detail with list of tests and their completion status.

    OOP — Composes ClientTestBriefSerializer (many=True) — composition.
    SRP — Only handles the category-detail view; listing view uses ClientCategorySerializer.
    """

    tests = serializers.SerializerMethodField()

    class Meta:
        model = CityTestCategory
        fields = ['id', 'name', 'description', 'tests']

    def get_tests(self, obj: CityTestCategory):
        """
        OOP — Passes serializer context down to nested serializer
              so it can compute is_completed per test.

        DIP — The nested serializer depends on the context abstraction,
              not on a hardcoded client lookup.
        """
        tests = obj.tests.order_by('order')
        return ClientTestBriefSerializer(
            tests, many=True, context=self.context
        ).data


class PreviousSubmissionSerializer(serializers.ModelSerializer):
    """
    Compact previous submission shown in the test detail endpoint.

    ISP — Shows only notes, question, and submitted_at. No internal IDs exposed.
    SRP — Separate from the admin submission listing serializer.
    """

    class Meta:
        model = CityTestSubmission
        fields = ['notes', 'question_for_liv_team', 'submitted_at']


class ClientCityTestDetailSerializer(serializers.ModelSerializer):
    """
    Full city test details shown when a client taps into a specific test.

    OOP — Composes PreviousSubmissionSerializer for the previous submission block.
    ISP — Returns everything the client needs to complete the test in one call.

    "Without ISP, if we returned the entire CityTest queryset including admin
     metadata (created_at, order) the client PWA would receive noise data that
     clutters the contract and increases payload size unnecessarily."
    """

    category_id      = serializers.CharField(source='category.id', read_only=True)
    previous_submission = serializers.SerializerMethodField()

    class Meta:
        model = CityTest
        fields = [
            'id',
            'category_id',
            'title',
            'short_description',
            'google_maps_link',
            'external_links',
            'note_prompts',
            'question_prompts',
            'previous_submission',
        ]

    def get_previous_submission(self, obj: CityTest):
        """
        OOP — Looks up the client's previous submission if it exists.
        SRP — This lookup is isolated here, not in the view.

        "Without SRP, if the view fetched the submission and passed it manually
         to the serializer, every new test endpoint would need to repeat that
         lookup pattern."
        """
        client = self.context.get('client')
        if client is None:
            return None
        try:
            sub = CityTestSubmission.objects.get(client=client, test=obj)
            return PreviousSubmissionSerializer(sub).data
        except CityTestSubmission.DoesNotExist:
            return None


# ── City Test Submission serializer ──────────────────────────────────────────

class CityTestSubmissionWriteSerializer(serializers.ModelSerializer):
    """
    Handles client's POST /city-tests/{test_id}/save request.

    SRP — Only validates the client's submission input.
    OCP — Adding optional fields (e.g., 'photos') means extending fields list.

    "Without SRP, if submission creation logic lived inside the view,
     adding field-level validation (e.g., links must be valid URLs)
     would scatter validation across the view method body."
    """

    class Meta:
        model = CityTestSubmission
        fields = ['notes', 'question_for_liv_team', 'links']
        extra_kwargs = {
            'notes': {'required': False},
            'question_for_liv_team': {'required': False},
            'links': {'required': False},
        }


# ── Admin submission listing serializer ──────────────────────────────────────

class AdminSubmissionListSerializer(serializers.ModelSerializer):
    """
    Admin-facing listing of all client test submissions.

    ISP — Admin sees client_name, test_title, category_id, etc.
          Clients never access this endpoint.
    SRP — Read-only admin listing view only.

    "Without ISP, exposing this serializer to clients would leak other
     clients' notes and questions — a serious privacy/data breach."
    """

    client_name   = serializers.CharField(source='client.full_name', read_only=True)
    user_id       = serializers.CharField(source='client.id', read_only=True)
    test_id       = serializers.CharField(source='test.id', read_only=True)
    test_title    = serializers.CharField(source='test.title', read_only=True)
    category_id   = serializers.CharField(source='test.category.id', read_only=True)
    category_name = serializers.CharField(source='test.category.name', read_only=True)

    class Meta:
        model = CityTestSubmission
        fields = [
            'id',
            'user_id',
            'client_name',
            'test_id',
            'test_title',
            'category_id',
            'category_name',
            'notes',
            'question_for_liv_team',
            'links',
            'submitted_at',
        ]


# =============================================================================
# SECTION 3: SOLO MICRO-TEST SERIALIZERS
# =============================================================================

class SoloMicroTestItemSerializer(serializers.ModelSerializer):
    """
    One solo micro-task item. SRP — one job: serialize a single task.
    ISP — client sees id, title, description only.
    """

    id = serializers.CharField(source='display_id', read_only=True)

    class Meta:
        model = SoloMicroTest
        fields = ['id', 'title', 'description']


class SoloMicroTestGroupSerializer(serializers.ModelSerializer):
    """
    A group with its nested list of items.

    OOP — Composition: nests SoloMicroTestItemSerializer.
    SRP — Groups the serializer; items are serialized by the nested class.

    "Without composition, duplicating all item fields inside the group serializer
     means a change to 'description' requires editing two serializers."
    """

    items = SoloMicroTestItemSerializer(many=True, read_only=True)

    class Meta:
        model = SoloMicroTestGroup
        fields = ['name', 'items']


class SoloMicroTestListSerializer(serializers.Serializer):
    """
    Top-level response for GET /api/app/solo-micro-tests.

    SRP — Only constructs the wrapper envelope (title, description, groups).
    OCP — Changing the title/description means changing only these fields here.

    OOP — Uses a plain Serializer (not ModelSerializer) because the response
          is a curated presentation, not a direct model dump.

    "Without OOP design clarity, returning raw queryset data would expose
     the group.order, group.id, and timestamps to the client —
     internal fields that belong to the admin, not the PWA."
    """

    title       = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    groups      = SoloMicroTestGroupSerializer(many=True, read_only=True)
