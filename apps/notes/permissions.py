"""Permissions for Notes access and mutations."""

from rest_framework import permissions

from apps.notes.models import Note, NoteVisibility
from apps.teams.models import TeamMembership, TeamRole


class CanViewNote(permissions.BasePermission):
    """Ensure user has read permission on a note (personal or team)."""

    def has_object_permission(self, request, view, obj: Note) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if obj.team is None:
            return obj.author_id == request.user.id

        membership = TeamMembership.objects.filter(team=obj.team, user=request.user).first()
        if not membership:
            return False

        if obj.visibility == NoteVisibility.PRIVATE:
            return obj.author_id == request.user.id or membership.role in [
                TeamRole.OWNER,
                TeamRole.ADMIN,
            ]

        return True


class CanEditNote(permissions.BasePermission):
    """Ensure user has write permission on a note."""

    def has_object_permission(self, request, view, obj: Note) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if obj.team is None:
            return obj.author_id == request.user.id

        membership = TeamMembership.objects.filter(team=obj.team, user=request.user).first()
        if not membership:
            return False

        if membership.role == TeamRole.VIEWER:
            return False

        if obj.visibility == NoteVisibility.PRIVATE:
            return obj.author_id == request.user.id or membership.role in [
                TeamRole.OWNER,
                TeamRole.ADMIN,
            ]

        return True


class CanDeleteNote(permissions.BasePermission):
    """Ensure user has delete permission on a note."""

    def has_object_permission(self, request, view, obj: Note) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if obj.team is None:
            return obj.author_id == request.user.id

        membership = TeamMembership.objects.filter(team=obj.team, user=request.user).first()
        if not membership:
            return False

        if membership.role in [TeamRole.OWNER, TeamRole.ADMIN]:
            return True

        return obj.author_id == request.user.id and membership.role == TeamRole.MEMBER
