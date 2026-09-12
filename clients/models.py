"""
clients/models.py

SOLID PRINCIPLE APPLIED:
- Single Responsibility Principle (SRP): Each model class is responsible for one
  domain entity only. Client manages client data, Trip manages trip data, etc.
  "Without SRP, one giant model would handle clients, trips, bookings all mixed
   together — making it impossible to change one without breaking another."

- Open/Closed Principle (OCP): Models use choice constants defined as class
  attributes, so adding new choices means extending, not modifying, the core logic.
  "Without OCP, adding a new relocation type would require searching through
   hardcoded string values scattered across views and serializers."

OOP APPLIED:
- AbstractTimestampedModel is a base abstract class providing created_at/updated_at
  to all models — a classic use of inheritance to avoid repetition.
"""

from django.db import models
from django.contrib.auth.models import User


# =============================================================================
# Abstract Base Model (OOP: Inheritance / SRP: timestamp concern isolated here)
# =============================================================================

class AbstractTimestampedModel(models.Model):
    """
    OOP — Abstract base class that provides created_at and updated_at fields.
    Every concrete model inherits from this so timestamp logic lives in one place.

    SRP — This class has ONE job: track when records are created/updated.
    "If we didn't use this abstract base, every model would repeat
     created_at/updated_at — violating DRY and making timestamp changes require
     editing every single model file."
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # Django will not create a table for this model


# =============================================================================
# Client Model
# =============================================================================

class Client(AbstractTimestampedModel):
    """
    Represents a Livable client.

    SRP — Handles only client profile data.
    OCP — The OneToOneField to User is optional; user creation logic lives in
          a separate service layer, not here.

    "Without SRP, we might shove trip data, financial profile data, and client
     data all into one bloated model — coupling everything together."
    """

    # Linked Django auth user (created when client is onboarded)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_profile',
        help_text="The portal login user linked to this client."
    )

    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50)
    target_destination = models.CharField(max_length=255)
    visa = models.CharField(max_length=255)
    target_arrival_timeline = models.CharField(
        max_length=100,
        default="October 2026 Arrival",
        help_text="e.g. October 2026 Arrival"
    )
    household_size = models.CharField(max_length=50)
    lead_advisor_name = models.CharField(max_length=255)
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"


# =============================================================================
# Trip Model
# =============================================================================

class Trip(AbstractTimestampedModel):
    """
    Represents a scouting trip created for a specific client.

    SRP — Trip only manages trip scheduling data; it delegates client info to
          the Client FK.
    OCP — New trip fields can be added without touching client or booking logic.

    "Without SRP, we might add trip data directly onto the Client model —
     making it impossible to have multiple trips per client and creating a
     messy, God Object."
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='trips',
        help_text="The client this trip belongs to."
    )
    city = models.CharField(max_length=255)
    # e.g. "Nov 12 - Nov 15, 2026"
    timeline = models.CharField(
        max_length=100,
        help_text="Human-readable date range, e.g. Nov 12 - Nov 15, 2026"
    )
    # pothoprodorshok er naam = Guide name (Bengali)
    guide_name = models.CharField(
        max_length=255,
        help_text="Guide name — pathoprodorshok er naam"
    )
    property_views = models.PositiveIntegerField(
        default=0,
        help_text="Number of properties planned to view during this trip."
    )

    class Meta:
        verbose_name = "Trip"
        verbose_name_plural = "Trips"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Trip for {self.client.full_name} to {self.city} ({self.timeline})"

    @property
    def is_upcoming(self):
        """
        OOP — Encapsulates business logic as a model property.
        Placeholder: real impl would parse the timeline string vs today's date.
        """
        return True


# =============================================================================
# Anonymous Booking Model
# =============================================================================

class AnonymousBooking(AbstractTimestampedModel):
    """
    Stores a booking submitted by an anonymous (unauthenticated) user.

    SRP — Completely separate from Client. An anonymous booking has its own
          lifecycle and may or may not convert into a full client.

    OCP — Choice lists are defined as class-level constants. Adding new options
          only means updating CHOICE lists, not modifying view or serializer logic.

    "Without OCP, if we hardcoded choice strings in multiple views and
     serializers, adding a new relocation option would require a grep across
     the entire codebase."
    """

    # OCP: Choice constants defined here; extending = just add a tuple
    RELOCATION_PROCESS_CHOICES = [
        ("just_exploring",      "Just starting to explore"),
        ("researching",         "Researching independently"),
        ("know_move_not_where", "I know I want to move, but not where"),
        ("specific_city",       "I have a specific city in mind"),
        ("ready_scouting",      "Ready to schedule a scouting trip"),
    ]

    SCOUTING_PEOPLE_CHOICES = [
        ("just_me",    "Just me"),
        ("two_people", "Two people"),
    ]

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=50)

    relocation_process_type = models.CharField(
        max_length=50,
        choices=RELOCATION_PROCESS_CHOICES,
        help_text="Where the user is in their relocation journey."
    )

    # Comma-separated place choices
    # OCP: To add a new place, just extend the FE choices constant — model stores value as-is
    considering_places_type = models.CharField(
        max_length=255,
        help_text=(
            "Comma-separated place choices: "
            "lisbon_porto | san_sebastian_malaga | valencia_malaga | not_sure"
        )
    )

    scouting_people_type = models.CharField(
        max_length=20,
        choices=SCOUTING_PEOPLE_CHOICES,
    )

    class Meta:
        verbose_name = "Anonymous Booking"
        verbose_name_plural = "Anonymous Bookings"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Anonymous Booking — {self.full_name} ({self.email})"


# =============================================================================
# Financial Profile Model
# =============================================================================

class FinancialProfile(AbstractTimestampedModel):
    """
    Detailed financial profile for a client.

    SRP — Financial data is completely isolated from lifestyle and trip data.
    LSP — This model can be passed anywhere AbstractTimestampedModel is expected.

    "Without SRP, mixing financial and lifestyle data in one model would create
     a 50-field monster that becomes impossible to maintain or query cleanly."
    """

    FINANCIAL_EXPECTATION_CHOICES = [
        ("maintain_lifestyle",   "Maintain my current spending while improving my lifestyle."),
        ("reduce_expenses",      "Reduce my monthly expenses while maintaining my current lifestyle."),
        ("spend_more_quality",   "Spend a little more to prioritize quality of life."),
        ("spend_less_compromise","Spend less, even if it means making compromises."),
        ("figuring_out",         "I'm still figuring that out."),
    ]

    INCOME_ROUTE_CHOICES = [
        ("remote_employment",  "Remote employment"),
        ("business_income",    "Business income"),
        ("retirement_pension", "Retirement or pension"),
        ("investment_income",  "Investment income"),
        ("figuring_out",       "Still figuring it out"),
    ]

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name='financial_profile',
        help_text="One financial profile per client."
    )

    # Multi-select stored as comma-separated keys
    # OCP: new motivations = add to FE list, model stores whatever string arrives
    motivating_factors = models.TextField(
        blank=True, default="",
        help_text=(
            "Comma-separated motivation keys: lower_costs | more_space | "
            "better_quality | financial_flexibility | retirement | remote_work | "
            "larger_runway | figuring_out"
        )
    )

    financial_note = models.TextField(blank=True, default="")

    comfortable_housing_budget = models.CharField(max_length=100, blank=True, default="")
    stretched_housing_budget = models.CharField(max_length=100, blank=True, default="")
    monthly_living_budget_target = models.CharField(max_length=100, blank=True, default="")

    share_your_opinion = models.TextField(blank=True, default="")
    general_monthly_living_budget_target = models.TextField(blank=True, default="")
    specific_codes_worried_about = models.TextField(blank=True, default="")

    financial_expectation = models.CharField(
        max_length=50, choices=FINANCIAL_EXPECTATION_CHOICES, blank=True, default=""
    )

    income_route = models.CharField(
        max_length=30, choices=INCOME_ROUTE_CHOICES, blank=True, default=""
    )
    income_route_note = models.TextField(blank=True, default="")

    # Multi-select: tradeoffs willing to make (comma-separated)
    willing_tradeoffs = models.TextField(
        blank=True, default="",
        help_text=(
            "Comma-separated: housing_size | commute_time | walkability | "
            "public_transport | nightlife | climate | distance_city_center | "
            "monthly_budget | peace_of_life | other"
        )
    )
    unwilling_tradeoffs_note = models.TextField(blank=True, default="")

    # Multi-select: practical constraints (comma-separated)
    practical_constraints = models.TextField(
        blank=True, default="",
        help_text=(
            "Comma-separated: buy_home | time_outside | children | pets | "
            "accessibility | tax_complexity | budget | other"
        )
    )
    practical_constraints_note = models.TextField(blank=True, default="")

    specific_cost_worries = models.TextField(blank=True, default="")

    # Multi-select: looking forward to financially
    financial_excitement_factors = models.TextField(
        blank=True, default="",
        help_text=(
            "Comma-separated: groceries | local_markets | no_car | "
            "public_transport | healthcare | dining | public_spaces | more_budget | other"
        )
    )
    financial_excitement_note = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Financial Profile"
        verbose_name_plural = "Financial Profiles"

    def __str__(self):
        return f"Financial Profile — {self.client.full_name}"


# =============================================================================
# Lifestyle Alignment Model
# =============================================================================

class LifestyleAlignment(AbstractTimestampedModel):
    """
    Captures lifestyle preferences and internal motivations of a client.

    SRP — Lifestyle concerns are completely separate from financial, trip, booking.
    ISP — Dashboard can fetch ONLY lifestyle data without loading unrelated models.

    "Without ISP, a single fat model would force every API response to carry
     ALL client data even when only lifestyle info is needed — wasting bandwidth
     and coupling unrelated concerns."
    """

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name='lifestyle_alignment',
        help_text="One lifestyle profile per client."
    )

    # Multi-select: daily life desires (comma-separated)
    daily_life_desires = models.TextField(
        blank=True, default="",
        help_text=(
            "Comma-separated: walking | outdoors | water_beaches | cafes | "
            "local_markets | language_learning | fitness | arts_culture | "
            "green_nature | slower_mornings | lively_evenings | community | "
            "deep_family | family_friendly | quiet | beauty | ease | other"
        )
    )

    good_weekday = models.TextField(blank=True, default="")
    good_weekend = models.TextField(blank=True, default="")
    routines_note = models.TextField(blank=True, default="")
    current_day_description = models.TextField(blank=True, default="")

    # Multi-select: environmental pull factors
    environmental_pull_factors = models.TextField(
        blank=True, default="",
        help_text=(
            "Comma-separated: outdoors | different_culture | slower_pace | "
            "beautiful_environment | natural_light | coast_access | explore_europe | "
            "outside_comfort_zone | comfortably_familiar | feels_like_me | other"
        )
    )
    environmental_pull_note = models.TextField(blank=True, default="")

    # Multi-select: internal pull factors
    internal_pull_factors = models.TextField(
        blank=True, default="",
        help_text=(
            "Comma-separated: brave | exciting | scary_good | calm | ready_change | "
            "always_meant | right_time | chance_grow | fresh_start | figuring_out | other"
        )
    )
    internal_pull_note = models.TextField(blank=True, default="")

    # Sincerity & Fear Check-in
    shadow_fear = models.TextField(
        blank=True, default="",
        help_text="The Shadow: What they are most afraid of / worried they might regret."
    )
    anchor_aspiration = models.TextField(
        blank=True, default="",
        help_text="The Anchor: The secret, specific thing their future European self will get."
    )

    # Positive vision
    success_picture = models.TextField(blank=True, default="")
    desired_emotions = models.TextField(blank=True, default="")
    glad_i_did_this_moment = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Lifestyle Alignment"
        verbose_name_plural = "Lifestyle Alignments"

    def __str__(self):
        return f"Lifestyle Alignment — {self.client.full_name}"
