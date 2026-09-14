"""
livable/models.py

SOLID PRINCIPLES APPLIED:
──────────────────────────────────────────────────────────────────────────────
S — Single Responsibility Principle:
    Each model class owns exactly one domain concept.
    • DailySchedule  → "a client's day plan" (date + client link)
    • ScheduleItem   → "one block of activity within a day"
    • CityTestCategory → "a grouping label for city tests"
    • CityTest       → "one specific test task in a category"
    • CityTestSubmission → "a client's response to a test"
    • SoloMicroTestGroup → "a named group of solo micro-tasks"
    • SoloMicroTest  → "one solo micro-task"

    "Without SRP, shoving schedule items, city-test metadata, and submissions
     into one model would mean changing a city-test prompt field accidentally
     drops a schedule item — tightly coupled chaos."

O — Open/Closed Principle:
    • ScheduleItem.ItemType choices are class-level constants.
      Adding a new type = extend the constant list, nothing else changes.
    • JSONField (external_links, note_prompts, question_prompts, links)
      is used for extensible arrays — the model doesn't need to change
      when the shape of these arrays evolves.

    "Without OCP, adding a new schedule type 'hotel' would require hunting
     through every view, serializer, and migration that hardcoded type strings."

L — Liskov Substitution Principle:
    All models safely inherit AbstractTimestampedModel — any code expecting
    a timestamped model works with any of these.

I — Interface Segregation Principle:
    ScheduleItem and CityTest are separate models even though both have
    google_maps_link. ISP says don't force models to carry fields they don't need.

    "Without ISP, one 'ContentBlock' model with all schedule AND city-test fields
     would be 40+ nullable columns — every query fetches irrelevant data."

D — Dependency Inversion Principle:
    Models depend on Django's abstract base (models.Model), not on concrete
    database drivers. Swapping DB backend = zero model changes.

OOP APPLIED:
    • AbstractTimestampedModel — base class (inheritance), DRY timestamps.
    • @property day_number on DailySchedule — encapsulated computed behavior.
    • __str__ on every model — polymorphic string representation.
"""

import uuid
from django.db import models
from clients.models import Client, AbstractTimestampedModel


# =============================================================================
# SECTION 1: TODAY / SCHEDULE MODELS
# =============================================================================

class DailySchedule(AbstractTimestampedModel):
    """
    Represents the complete schedule for ONE client on ONE date.

    SRP — Owns only the date + client association. Individual time-blocks
          live in ScheduleItem (separate model, separate responsibility).

    OCP — New schedule metadata (e.g., city, weather note) can be added
          here without touching ScheduleItem.

    "Without SRP, embedding all items as a JSON blob on DailySchedule would
     make editing a single item require re-POSTing the entire day's schedule."
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='daily_schedules',
        help_text="The client this schedule belongs to.",
    )
    date = models.DateField(help_text="The date of this schedule (YYYY-MM-DD).")

    class Meta:
        verbose_name = "Daily Schedule"
        verbose_name_plural = "Daily Schedules"
        # OCP: unique_together enforces one schedule per client per date
        # Adding a "city" dimension later = just update this constraint here.
        unique_together = [('client', 'date')]
        ordering = ['date']

    def __str__(self):
        return f"Schedule for {self.client.full_name} on {self.date}"

    @property
    def day_number(self) -> int:
        """
        OOP — Encapsulated computed property. Calculates which day of the
        trip this schedule falls on (1-indexed from earliest schedule).

        SRP — Day-number logic lives here, not duplicated in every view.
        "Without encapsulation, every view that needs day_number would
         re-implement this date arithmetic — inconsistencies guaranteed."
        """
        earliest = (
            DailySchedule.objects
            .filter(client=self.client)
            .order_by('date')
            .values_list('date', flat=True)
            .first()
        )
        if earliest is None:
            return 1
        return (self.date - earliest).days + 1


class ScheduleItem(AbstractTimestampedModel):
    """
    One time-block/activity within a DailySchedule.

    SRP — Owns only a single activity's data. DailySchedule owns the day.
    OCP — New item types are added by extending ItemType choices.

    "Without OCP, adding an 'open_time' type would require changing validation
     logic in 3 different view methods that hardcoded the type string."
    """

    # OCP: choice constants — extend here, nothing else changes
    class ItemType(models.TextChoices):
        MEETING        = 'meeting',        'Meeting'
        RECOMMENDATION = 'recommendation', 'Recommendation'
        OPEN_TIME      = 'open_time',      'Open Time'
        HOTEL          = 'hotel',          'Hotel'

    # OOP: UUIDField for globally unique item identification across all schedules
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key — safe to expose in API responses.",
    )

    schedule = models.ForeignKey(
        DailySchedule,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="The daily schedule this item belongs to.",
    )

    # Time fields — stored as strings matching "HH:MM" UI format
    start_time = models.CharField(
        max_length=5,
        help_text="Start time in HH:MM format, e.g. 09:00",
    )
    end_time = models.CharField(
        max_length=5,
        null=True,
        blank=True,
        help_text="End time in HH:MM format, e.g. 11:00",
    )

    title = models.CharField(max_length=255)

    item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.MEETING,
        help_text="Type of schedule item.",
    )

    short_description = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Brief summary shown in the collapsed list view.",
    )

    # Detail fields (shown when item is expanded)
    description   = models.TextField(blank=True, default="")
    host_name     = models.CharField(max_length=255, blank=True, default="")
    meeting_point = models.CharField(max_length=500, blank=True, default="")
    what_to_bring = models.CharField(max_length=500, blank=True, default="")
    google_maps_link  = models.URLField(blank=True, default="")
    restaurant_link   = models.URLField(blank=True, null=True, default=None)
    phone    = models.CharField(max_length=50, blank=True, null=True, default=None)
    website  = models.URLField(blank=True, null=True, default=None)
    reminder = models.CharField(max_length=500, blank=True, null=True, default=None)

    # ordering within a day
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Controls display order within the day."
    )

    class Meta:
        verbose_name = "Schedule Item"
        verbose_name_plural = "Schedule Items"
        ordering = ['order', 'start_time']

    def __str__(self):
        return f"[{self.schedule.date}] {self.start_time} – {self.title}"

    @property
    def is_expandable(self) -> bool:
        """
        OOP — Computed property. An item is expandable if it has any detail
        fields beyond the short_description.

        SRP — Expandability logic lives here, not in the serializer.
        "Without encapsulation, every serializer and view would repeat
         'if description or host_name or ...' logic everywhere."
        """
        return bool(
            self.description
            or self.host_name
            or self.meeting_point
            or self.what_to_bring
            or self.google_maps_link
            or self.restaurant_link
            or self.phone
            or self.website
        )


# =============================================================================
# SECTION 2: CITY TESTS MODELS
# =============================================================================

class CityTestCategory(AbstractTimestampedModel):
    """
    A category grouping city tests (e.g. food, free_time, infrastructure).

    SRP — Owns only category metadata (name, description).
          Tests that belong to it live in CityTest.

    OCP — New categories are added as new records, not by changing code.

    "Without SRP, embedding category name/description as a CharField on
     CityTest would mean updating a category name requires updating every
     single CityTest row — a maintenance nightmare."
    """

    # slug-style id (e.g. "food", "free_time", "infrastructure")
    id = models.CharField(
        max_length=50,
        primary_key=True,
        help_text="Slug identifier, e.g. 'food', 'free_time', 'infrastructure'",
    )
    name = models.CharField(max_length=255, help_text="Human-readable category name.")
    description = models.TextField(blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "City Test Category"
        verbose_name_plural = "City Test Categories"
        ordering = ['order']

    def __str__(self):
        return self.name


class CityTest(AbstractTimestampedModel):
    """
    A single structured 'test' task within a category.
    e.g. "Everyday Lunch", "Bakery Run", "Market Morning".

    SRP — Owns only test definition data (prompts, links, ordering).
          Client responses live in CityTestSubmission.

    OCP — external_links, note_prompts, question_prompts are JSONField arrays.
          The shape of these arrays can evolve without a schema migration.

    "Without OCP, if note_prompts were separate rows in a NotePrompt model,
     adding a new prompt type would require a migration and a new model class.
     JSONField keeps the schema stable while the content evolves."

    ISP — CityTest does NOT carry submission data. Clients fetching a test
          definition are not burdened with other users' submission history.

    "Without ISP, embedding all submissions in the CityTest model would make
     every test detail API call load potentially thousands of submission rows."
    """

    # slug id matching the API spec (e.g. "everyday-lunch")
    id = models.SlugField(
        max_length=100,
        primary_key=True,
        help_text="Slug identifier, e.g. 'everyday-lunch'",
    )

    category = models.ForeignKey(
        CityTestCategory,
        on_delete=models.CASCADE,
        related_name='tests',
        help_text="The category this test belongs to.",
    )

    title = models.CharField(max_length=255)
    city = models.CharField(max_length=100, blank=True, default="")
    short_description = models.TextField(blank=True, default="")
    google_maps_link  = models.URLField(blank=True, default="")

    # JSONField arrays — OCP: shape can change without model/migration changes
    external_links = models.JSONField(
        default=list,
        blank=True,
        help_text='Array of {"label": str, "url": str} objects.',
    )
    note_prompts = models.JSONField(
        default=list,
        blank=True,
        help_text='Array of prompt strings shown to guide user notes.',
    )
    question_prompts = models.JSONField(
        default=list,
        blank=True,
        help_text='Array of question strings the client should answer for the Liv team.',
    )

    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order within the category.",
    )

    class Meta:
        verbose_name = "City Test"
        verbose_name_plural = "City Tests"
        ordering = ['category', 'order']

    def __str__(self):
        return f"[{self.category_id}] {self.title}"


class CityTestSubmission(AbstractTimestampedModel):
    """
    A client's saved notes and questions for a specific CityTest.

    SRP — Owns only the client's submission. CityTest owns the template.
    OCP — The links field is a JSONField array so clients can attach
          any number of links without a schema change.

    "Without SRP, storing submission data directly on CityTest would
     mean one client's notes overwrite another's — a catastrophic bug."

    DIP — Depends on Client and CityTest FKs (abstractions), not on
          specific user/test implementation details.
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='city_test_submissions',
    )
    test = models.ForeignKey(
        CityTest,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    notes = models.TextField(blank=True, default="")
    question_for_liv_team = models.TextField(blank=True, default="")
    # OCP: JSONField array — clients can attach N links, no schema change needed
    links = models.JSONField(
        default=list,
        blank=True,
        help_text='Array of URL strings the client wants to save.',
    )
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "City Test Submission"
        verbose_name_plural = "City Test Submissions"
        # ISP: Each client has at most one submission per test.
        # If multiple submissions per client are needed later, remove this
        # and add a 'is_latest' flag — OCP: extend, don't modify.
        unique_together = [('client', 'test')]
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Submission by {self.client.full_name} for {self.test.title}"


# =============================================================================
# SECTION 3: SOLO DISCOVERY MICRO-TESTS
# =============================================================================

class SoloMicroTestGroup(AbstractTimestampedModel):
    """
    A named group of solo micro-tasks (e.g. "Social Infrastructure").

    SRP — Owns only the group name and ordering.
          The individual tasks live in SoloMicroTest.

    OCP — New groups are added as new records; no code change needed.

    "Without SRP, embedding the group name on every SoloMicroTest row
     means renaming a group requires updating dozens of rows — brittle."
    """

    name  = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Solo Micro-Test Group"
        verbose_name_plural = "Solo Micro-Test Groups"
        ordering = ['order']

    def __str__(self):
        return self.name


class SoloMicroTest(AbstractTimestampedModel):
    """
    One solo discovery micro-task within a group.
    e.g. { id: "01", title: "After-Work Drinks", description: "..." }

    SRP — Owns only task identity and description.
    OCP — New tasks are added as records; no serializer or view changes needed.

    ISP — Clients fetching solo tests only get task id/title/description.
          They are not burdened with admin-only metadata.

    "Without ISP, including admin-only fields (created_by, last_edited, etc.)
     in the same model without a dedicated read serializer would expose
     internal metadata to every client API call."
    """

    group = models.ForeignKey(
        SoloMicroTestGroup,
        on_delete=models.CASCADE,
        related_name='items',
    )
    # Short display id (e.g. "01", "02")
    display_id  = models.CharField(max_length=10)
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Solo Micro-Test"
        verbose_name_plural = "Solo Micro-Tests"
        ordering = ['group__order', 'order']

    def __str__(self):
        return f"[{self.group.name}] {self.display_id} – {self.title}"
