"""
authapp/models.py

The authapp uses Django's built-in User model for authentication.
No custom models needed here — keeping SRP: auth models live in Django's
contrib.auth, not duplicated here.

OCP: If a custom user model is needed in future, extend AbstractUser
     in this file and set AUTH_USER_MODEL in settings.py — no other
     changes required throughout the codebase.

"Without OCP planning, switching to a custom user model later would require
 rewriting every ForeignKey to User across the entire codebase."
"""

# No custom models — Django contrib.auth.models.User is used directly.
# This is intentional: SRP means we don't duplicate auth model concerns.
