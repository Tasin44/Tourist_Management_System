"""
clients/apps.py

SRP: App config has one job — configure the clients Django application.
"""

from django.apps import AppConfig


class ClientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clients'
    verbose_name = 'Livable Clients'
