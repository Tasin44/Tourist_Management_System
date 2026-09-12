"""
clients/services.py

SOLID PRINCIPLE APPLIED:
- Single Responsibility Principle (SRP): Each service class does ONE thing.
  ClientCreationService only handles client creation + user provisioning + email.
  "Without SRP, if we put user creation, password generation, and email sending
   all inside the view, the view would become untestable and unmaintainable."

- Open/Closed Principle (OCP): EmailService and PasswordService are injected,
  meaning we can swap them (e.g., switch to SendGrid) without touching the
  ClientCreationService class itself.
  "Without OCP, changing from console email to SendGrid would require editing
   ClientCreationService directly — risking regressions."

- Dependency Inversion Principle (DIP): High-level ClientCreationService depends
  on the abstract interface (duck-typed EmailService/PasswordService), not on
  concrete Django implementations directly.
  "Without DIP, testing ClientCreationService would require a real SMTP server
   because the email logic would be hardcoded inside the service."

OOP APPLIED:
- Services are Python classes with clear __init__ and single public methods,
  encapsulating state and behavior together.
"""

import secrets
import string
import logging

from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

from .models import Client

logger = logging.getLogger(__name__)


# =============================================================================
# Password Generator Service
# SRP: Only responsible for generating secure random passwords.
# =============================================================================

class PasswordGeneratorService:
    """
    SRP — Has one job: generate a cryptographically random password.

    OCP — Password complexity rules can be extended (e.g., add symbols) without
          changing the interface.

    "Without SRP, password generation logic scattered inside views means every
     test must replicate password logic instead of mocking one service."
    """

    def __init__(self, length: int = 12):
        # DIP: length is injected, making this configurable without subclassing
        self.length = length

    def generate(self) -> str:
        """
        OOP — Encapsulates the password alphabet and generation logic.
        Uses secrets module for cryptographic security.
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(self.length))


# =============================================================================
# Email Service
# SRP: Only responsible for sending the welcome / credential email.
# DIP: Relies on Django's send_mail abstraction, not a specific SMTP impl.
# =============================================================================

class ClientWelcomeEmailService:
    """
    SRP — Has one job: compose and send the welcome email to a new client.

    DIP — Uses Django's send_mail which is backed by whatever EMAIL_BACKEND is
          configured in settings. Swapping backends = no code change here.

    "Without DIP, if we directly called smtplib here, switching to SendGrid
     would require rewriting this entire class."
    """

    # OCP: subject/from_email can be overridden in subclass for customization
    SUBJECT = "Welcome to Livable — Your Account Details"
    FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@livable.com')

    def send(self, email: str, password: str, client_name: str) -> None:
        """
        Sends a welcome email with temporary login credentials.

        Args:
            email: Client's email address
            password: The generated temporary password
            client_name: Client's full name for personalisation
        """
        # SRP: message composition is isolated here, not in the view
        message = self._compose_message(email=email, password=password, client_name=client_name)
        try:
            send_mail(
                subject=self.SUBJECT,
                message=message,
                from_email=self.FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info("Welcome email sent to %s", email)
        except Exception as exc:
            # Log but don't crash client creation over an email failure
            logger.error("Failed to send welcome email to %s: %s", email, exc)

    @staticmethod
    def _compose_message(email: str, password: str, client_name: str) -> str:
        """
        OOP — Private method encapsulates message template.
        SRP — If the template changes, only this method changes.
        """
        return (
            f"Hi {client_name},\n\n"
            "The Livable team has created your account. "
            "Here are your login credentials:\n\n"
            f"  Email:    {email}\n"
            f"  Password: {password}\n\n"
            "Please reset this password upon first login.\n\n"
            "Welcome aboard,\n"
            "The Livable Team"
        )


# =============================================================================
# Client Creation Service
# SRP: Orchestrates client creation + Django User provisioning + welcome email.
# DIP: Receives PasswordGeneratorService and EmailService as dependencies.
# =============================================================================

class ClientCreationService:
    """
    Orchestrates the full client onboarding flow:
      1. Create Client record
      2. Create Django User (for portal login)
      3. Send welcome email with temporary credentials

    SRP — This service owns ONLY the orchestration of these three steps.
          It does NOT know how passwords are generated or how emails are sent.

    DIP — Password generator and email sender are injected via __init__,
          so tests can inject mocks without touching production code.

    "Without DIP, unit testing this service would require a live database and
     a real SMTP server — making tests slow and fragile."
    """

    def __init__(
        self,
        password_service: PasswordGeneratorService = None,
        email_service: ClientWelcomeEmailService = None,
    ):
        # DIP: inject dependencies, fall back to defaults if not provided
        self.password_service = password_service or PasswordGeneratorService()
        self.email_service = email_service or ClientWelcomeEmailService()

    def create(self, validated_data: dict) -> Client:
        """
        Creates a Client, a linked User, and sends the welcome email.

        OOP — Single public method; internal steps are private methods.

        Args:
            validated_data: Cleaned data from ClientSerializer

        Returns:
            The newly created Client instance
        """
        raw_password = self.password_service.generate()

        # Step 1: Create Django User for portal access
        user = self._create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            raw_password=raw_password,
        )

        # Step 2: Create the Client record linked to the User
        client = Client.objects.create(user=user, **validated_data)

        # Step 3: Send welcome email with credentials
        self.email_service.send(
            email=validated_data['email'],
            password=raw_password,
            client_name=validated_data['full_name'],
        )

        return client

    @staticmethod
    def _create_user(email: str, full_name: str, raw_password: str) -> User:
        """
        OOP — Private helper encapsulates User creation detail.
        SRP — User creation responsibility is isolated here.
        """
        username = email  # Use email as username for simplicity
        name_parts = full_name.strip().split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        user = User.objects.create_user(
            username=username,
            email=email,
            password=raw_password,
            first_name=first_name,
            last_name=last_name,
        )
        return user
