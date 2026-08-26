"""Team-level authorization and permission classes."""

from rest_framework import permissions

from apps.teams.models import Team, TeamMembership, TeamRole


class IsTeamMember(permissions.BasePermission):
    """Allows access only to authenticated users who are members of the team."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        team = obj if isinstance(obj, Team) else getattr(obj, "team", None)
        if team is None:
            return True  # If not a team-scoped object, let other permission handle

        return TeamMembership.objects.filter(team=team, user=request.user).exists()


class IsTeamAdminOrOwner(permissions.BasePermission):
    """Allows access only to team admins or owners."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        team = obj if isinstance(obj, Team) else getattr(obj, "team", None)
        if team is None:
            return False

        return TeamMembership.objects.filter(
            team=team,
            user=request.user,
            role__in=[TeamRole.OWNER, TeamRole.ADMIN],
        ).exists()


class IsTeamOwner(permissions.BasePermission):
    """Allows access only to team owners."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        team = obj if isinstance(obj, Team) else getattr(obj, "team", None)
        if team is None:
            return False

        return TeamMembership.objects.filter(
            team=team,
            user=request.user,
            role=TeamRole.OWNER,
        ).exists()
