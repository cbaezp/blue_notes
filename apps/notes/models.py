"""Notes, Tags, and Note Revisions domain models."""

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDPrimaryKeyModel
from apps.teams.models import Team


class Tag(UUIDPrimaryKeyModel, TimeStampedModel):
    """Categorical tag for notes, optionally scoped to a team workspace."""

    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default="#3B82F6")  # Hex color
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, blank=True, related_name="tags"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tags",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "name"],
                condition=models.Q(team__isnull=False),
                name="unique_team_tag_name",
            ),
            models.UniqueConstraint(
                fields=["created_by", "name"],
                condition=models.Q(team__isnull=True),
                name="unique_personal_tag_name",
            ),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({'Personal' if self.team is None else self.team.name})"


class NoteVisibility(models.TextChoices):
    TEAM = "TEAM", "Team"
    PRIVATE = "PRIVATE", "Private"


class Note(UUIDPrimaryKeyModel, TimeStampedModel, SoftDeleteModel):
    """Core Note entity with Optimistic Concurrency Control and Search."""

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notes",
        db_index=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
        db_index=True,
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    visibility = models.CharField(
        max_length=20,
        choices=NoteVisibility.choices,
        default=NoteVisibility.TEAM,
    )
    version = models.PositiveIntegerField(default=1)  # Optimistic Concurrency Control
    is_pinned = models.BooleanField(default=False, db_index=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="notes")
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="note_search_vector_gin"),
            models.Index(fields=["team", "is_pinned", "-created_at"], name="note_team_pinned_idx"),
            models.Index(fields=["author", "team", "deleted_at"], name="note_author_team_del_idx"),
        ]
        ordering = ["-is_pinned", "-updated_at"]

    def __str__(self) -> str:
        return f"{self.title} (v{self.version})"

    @property
    def is_personal(self) -> bool:
        return self.team is None


class NoteVersion(UUIDPrimaryKeyModel, TimeStampedModel):
    """Immutable snapshot of a note revision for audit and restore."""

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="history")
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="note_revisions",
    )
    change_summary = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["note", "version_number"],
                name="unique_note_version",
            )
        ]
        ordering = ["-version_number"]

    def __str__(self) -> str:
        return f"{self.note.title} - v{self.version_number}"
