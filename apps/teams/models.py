"""Team and TeamMembership multi-tenant models."""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDPrimaryKeyModel


class TeamRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    MEMBER = "MEMBER", "Member"
    VIEWER = "VIEWER", "Viewer"


class Team(UUIDPrimaryKeyModel, TimeStampedModel):
    """Multi-tenant boundary for small teams."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_teams",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="TeamMembership",
        related_name="teams",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class TeamMembership(UUIDPrimaryKeyModel, TimeStampedModel):
    """Association between User and Team with specific RBAC role."""

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=TeamRole.choices,
        default=TeamRole.MEMBER,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="unique_team_user_membership")
        ]
        ordering = ["role", "-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role}) in {self.team.name}"
