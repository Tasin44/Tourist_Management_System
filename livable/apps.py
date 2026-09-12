"""
livable/apps.py

SRP: App config has one job — configure the livable Django application.
"""

from django.apps import AppConfig


class LiveableConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'livable'
    verbose_name = 'Livable App (Schedule + City Tests)'
