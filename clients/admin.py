"""
clients/admin.py

Django admin registration for all clients app models.

SRP: Admin config has one job — register models for the Django admin panel.
OCP: New models are registered by adding new ModelAdmin classes, not editing existing ones.
"""

from django.contrib import admin

from .models import (
    Client,
    Trip,
    AnonymousBooking,
    FinancialProfile,
    LifestyleAlignment,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    SRP — Only configures admin display for Client.
    OCP — Extending list_display is done here; view logic is untouched.
    """
    list_display = [
        'full_name', 'email', 'phone', 'target_destination',
        'lead_advisor_name', 'created_at',
    ]
    search_fields = ['full_name', 'email', 'lead_advisor_name']
    list_filter = ['target_destination', 'visa']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    """SRP — Only configures admin display for Trip."""
    list_display = ['client', 'city', 'timeline', 'guide_name', 'property_views', 'created_at']
    search_fields = ['client__full_name', 'city', 'guide_name']
    list_filter = ['city']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AnonymousBooking)
class AnonymousBookingAdmin(admin.ModelAdmin):
    """SRP — Only configures admin display for AnonymousBooking."""
    list_display = ['full_name', 'email', 'phone_number', 'relocation_process_type', 'created_at']
    search_fields = ['full_name', 'email']
    list_filter = ['relocation_process_type', 'scouting_people_type']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FinancialProfile)
class FinancialProfileAdmin(admin.ModelAdmin):
    """SRP — Only configures admin display for FinancialProfile."""
    list_display = ['client', 'financial_expectation', 'income_route', 'created_at']
    search_fields = ['client__full_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LifestyleAlignment)
class LifestyleAlignmentAdmin(admin.ModelAdmin):
    """SRP — Only configures admin display for LifestyleAlignment."""
    list_display = ['client', 'created_at', 'updated_at']
    search_fields = ['client__full_name']
    readonly_fields = ['created_at', 'updated_at']
