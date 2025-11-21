from rest_framework import permissions
from .models import UserRole


class IsStaff(permissions.BasePermission):
    """Permission check for Staff role"""
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role == UserRole.STAFF
        )


class IsApproverLevel1(permissions.BasePermission):
    """Permission check for Approver Level 1 role"""
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role == UserRole.APPROVER_L1
        )


class IsApproverLevel2(permissions.BasePermission):
    """Permission check for Approver Level 2 role"""
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role == UserRole.APPROVER_L2
        )


class IsAnyApprover(permissions.BasePermission):
    """Permission check for any Approver role (Level 1 or 2)"""
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role in [UserRole.APPROVER_L1, UserRole.APPROVER_L2]
        )


class IsFinance(permissions.BasePermission):
    """Permission check for Finance role"""
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role == UserRole.FINANCE
        )


class IsRequestOwner(permissions.BasePermission):
    """Permission check for request owner"""
    def has_object_permission(self, request, view, obj):
        return obj.created_by == request.user


class CanEditRequest(permissions.BasePermission):
    """Permission check for editing a request (owner + pending status)"""
    def has_object_permission(self, request, view, obj):
        return obj.can_be_edited_by(request.user)
