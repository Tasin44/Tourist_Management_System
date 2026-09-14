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

# No custom user model — Django contrib.auth.models.User is used directly.
from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"
