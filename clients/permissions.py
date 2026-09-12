"""
clients/permissions.py

SOLID PRINCIPLE APPLIED:
- Single Responsibility Principle (SRP): Each permission class has ONE job.
  IsAdminUser checks admin status, IsClientOwner checks ownership.
  "Without SRP, putting permission logic inside views means every view
   repeats ownership checks — and a security fix must be applied in N places."

- Open/Closed Principle (OCP): New permissions are added as new classes,
  not by modifying existing ones.
  "Without OCP, adding a 'staff can view all' rule would require editing
   every single view's permission logic."

OOP APPLIED:
- Custom permissions inherit from BasePermission, overriding has_permission
  and has_object_permission — a clean use of polymorphism.
"""

from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS


# =============================================================================
# IsAdminUser Permission
# SRP: Only checks if the authenticated user is an admin/staff.
# =============================================================================

class IsAdminUser(BasePermission):
    """
    Grants access only to Django admin/staff users.

    SRP — One responsibility: check admin status.
    OCP — If 'admin' definition changes (e.g., via a role model), only this
          class needs updating.

    "Without SRP, if every view does `if request.user.is_staff: ...`, changing
     the admin check requires touching every view."
    """

    message = "Admin access required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


# =============================================================================
# IsClientOwner Permission
# SRP: Only checks if the authenticated user owns the client resource.
# =============================================================================

class IsClientOwner(BasePermission):
    """
    Grants access only if the requesting user's Client profile matches
    the Client being accessed.

    SRP — Ownership check is isolated here, not repeated in every view.
    OOP — has_object_permission receives the object and performs ownership check.

    "Without SRP, each client detail view would duplicate: 
     if client.user != request.user: raise PermissionDenied
     — scattered checks that are easy to forget in new views."
    """

    message = "You can only access your own data."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """
        OOP — Polymorphically handles both Client and Trip objects:
              - For Client: check obj.user == request.user
              - For Trip: check obj.client.user == request.user
        """
        from .models import Client, Trip  # local import avoids circular deps

        if isinstance(obj, Client):
            return obj.user == request.user

        if isinstance(obj, Trip):
            return obj.client.user == request.user

        return False


# =============================================================================
# IsAdminOrClientOwner Permission
# OCP: Combines rules by composition — no existing class is modified.
# SRP: Composed from existing atomic permissions, not a new monolithic class.
# =============================================================================

class IsAdminOrClientOwner(BasePermission):
    """
    Grants access if the user is an admin OR the client owner.

    OCP — Extends permission logic by composing IsAdminUser and IsClientOwner
          without modifying either.

    "Without OCP, we'd add `or request.user.is_staff` conditions inside
     IsClientOwner — making it handle two responsibilities and harder to test."
    """

    message = "You must be an admin or the client owner."

    def __init__(self):
        self._admin_perm = IsAdminUser()
        self._owner_perm = IsClientOwner()

    def has_permission(self, request, view):
        return (
            self._admin_perm.has_permission(request, view)
            or self._owner_perm.has_permission(request, view)
        )

    def has_object_permission(self, request, view, obj):
        return (
            self._admin_perm.has_permission(request, view)
            or self._owner_perm.has_object_permission(request, view, obj)
        )
