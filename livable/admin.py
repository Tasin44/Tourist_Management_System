"""
livable/admin.py

Django admin registration for all livable app models.

SRP: Admin config has one job — register models for the Django admin panel.
OCP: New models are registered by adding new ModelAdmin classes, not editing existing ones.
"""

from django.contrib import admin
from .models import (
    DailySchedule,
    ScheduleItem,
    CityTestCategory,
    CityTest,
    CityTestSubmission,
    SoloMicroTestGroup,
    SoloMicroTest,
)


class ScheduleItemInline(admin.TabularInline):
    """
    OOP: Inline admin class — composition of ScheduleItem inside DailySchedule admin.
    SRP: Only configures the inline display, not the full admin.
    """
    model = ScheduleItem
    extra = 1
    fields = ['start_time', 'end_time', 'title', 'item_type', 'short_description', 'order']


@admin.register(DailySchedule)
class DailyScheduleAdmin(admin.ModelAdmin):
    """SRP — Only configures admin display for DailySchedule."""
    list_display  = ['client', 'date', 'created_at']
    list_filter   = ['date']
    search_fields = ['client__full_name']
    inlines       = [ScheduleItemInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ScheduleItem)
class ScheduleItemAdmin(admin.ModelAdmin):
    """SRP — Standalone schedule item admin for direct editing."""
    list_display  = ['title', 'schedule', 'start_time', 'end_time', 'item_type']
    list_filter   = ['item_type']
    search_fields = ['title', 'schedule__client__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']


class CityTestInline(admin.TabularInline):
    """OOP: Inline — shows city tests inside their category admin page."""
    model  = CityTest
    extra  = 0
    fields = ['id', 'title', 'order']


@admin.register(CityTestCategory)
class CityTestCategoryAdmin(admin.ModelAdmin):
    """SRP — Admin display for CityTestCategory."""
    list_display  = ['id', 'name', 'order']
    search_fields = ['name']
    inlines       = [CityTestInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CityTest)
class CityTestAdmin(admin.ModelAdmin):
    """SRP — Admin display for CityTest."""
    list_display  = ['id', 'title', 'category', 'order']
    list_filter   = ['category']
    search_fields = ['title', 'id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CityTestSubmission)
class CityTestSubmissionAdmin(admin.ModelAdmin):
    """SRP — Admin display for CityTestSubmission."""
    list_display  = ['client', 'test', 'submitted_at']
    list_filter   = ['test__category']
    search_fields = ['client__full_name', 'test__title']
    readonly_fields = ['submitted_at', 'created_at', 'updated_at']


class SoloMicroTestInline(admin.TabularInline):
    """OOP: Inline — shows micro-tests inside their group admin page."""
    model  = SoloMicroTest
    extra  = 1
    fields = ['display_id', 'title', 'description', 'order']


@admin.register(SoloMicroTestGroup)
class SoloMicroTestGroupAdmin(admin.ModelAdmin):
    """SRP — Admin display for SoloMicroTestGroup."""
    list_display  = ['name', 'order']
    inlines       = [SoloMicroTestInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SoloMicroTest)
class SoloMicroTestAdmin(admin.ModelAdmin):
    """SRP — Standalone admin for SoloMicroTest."""
    list_display  = ['display_id', 'title', 'group', 'order']
    list_filter   = ['group']
    search_fields = ['title']
    readonly_fields = ['created_at', 'updated_at']
