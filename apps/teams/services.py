"""Business logic services for team lifecycle and membership management."""

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.core.exceptions import PermissionDeniedError, ValidationError
from apps.teams.models import Team, TeamMembership, TeamRole

User = get_user_model()


@transaction.atomic
def team_create(*, name: str, description: str = "", created_by: User) -> Team:
    """Create a new team and automatically assign the creator as OWNER."""
    team = Team.objects.create(name=name, description=description, created_by=created_by)
    TeamMembership.objects.create(team=team, user=created_by, role=TeamRole.OWNER)
    return team


@transaction.atomic
def team_add_member(
    *, team: Team, user: User, role: str = TeamRole.MEMBER, acting_user: User
) -> TeamMembership:
    """Add a new member to the team with authorization validation."""
    actor_membership = TeamMembership.objects.filter(team=team, user=acting_user).first()
    if not actor_membership or actor_membership.role not in [TeamRole.OWNER, TeamRole.ADMIN]:
        raise PermissionDeniedError("Only team owners and admins can add members.")

    if TeamMembership.objects.filter(team=team, user=user).exists():
        raise ValidationError("User is already a member of this team.")

    if role == TeamRole.OWNER and actor_membership.role != TeamRole.OWNER:
        raise PermissionDeniedError("Only team owners can grant OWNER role.")

    return TeamMembership.objects.create(team=team, user=user, role=role)


@transaction.atomic
def team_update_member_role(
    *, team: Team, target_user: User, new_role: str, acting_user: User
) -> TeamMembership:
    """Update role of an existing team member with role hierarchy checks."""
    actor_membership = TeamMembership.objects.filter(team=team, user=acting_user).first()
    if not actor_membership or actor_membership.role not in [TeamRole.OWNER, TeamRole.ADMIN]:
        raise PermissionDeniedError("Only team owners and admins can update member roles.")

    target_membership = TeamMembership.objects.filter(team=team, user=target_user).first()
    if not target_membership:
        raise ValidationError("Target user is not a member of this team.")

    # Only owners can change owner roles or promote to owner
    if (
        target_membership.role == TeamRole.OWNER or new_role == TeamRole.OWNER
    ) and actor_membership.role != TeamRole.OWNER:
        raise PermissionDeniedError("Only team owners can manage OWNER role assignments.")

    # Ensure at least one owner remains
    if target_membership.role == TeamRole.OWNER and new_role != TeamRole.OWNER:
        other_owners = (
            TeamMembership.objects.filter(team=team, role=TeamRole.OWNER)
            .exclude(user=target_user)
            .exists()
        )
        if not other_owners:
            raise ValidationError("Cannot demote the sole team owner.")

    target_membership.role = new_role
    target_membership.save(update_fields=["role", "updated_at"])
    return target_membership


@transaction.atomic
def team_remove_member(*, team: Team, target_user: User, acting_user: User) -> None:
    """Remove a user from a team with guard against removing the last owner."""
    actor_membership = TeamMembership.objects.filter(team=team, user=acting_user).first()
    is_self_removal = target_user == acting_user

    if not is_self_removal and (
        not actor_membership or actor_membership.role not in [TeamRole.OWNER, TeamRole.ADMIN]
    ):
        raise PermissionDeniedError("Only team owners and admins can remove other members.")

    target_membership = TeamMembership.objects.filter(team=team, user=target_user).first()
    if not target_membership:
        raise ValidationError("Target user is not a member of this team.")

    if target_membership.role == TeamRole.OWNER:
        other_owners = (
            TeamMembership.objects.filter(team=team, role=TeamRole.OWNER)
            .exclude(user=target_user)
            .exists()
        )
        if not other_owners:
            raise ValidationError("Cannot remove the sole team owner. Transfer ownership first.")

    target_membership.delete()
