"""Business logic services for Note lifecycle, OCC mutations, and revisions."""

from collections.abc import Iterable

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVector
from django.db import transaction

from apps.core.exceptions import ConflictError, PermissionDeniedError, ValidationError
from apps.notes.models import Note, NoteVersion, NoteVisibility, Tag
from apps.teams.models import Team, TeamMembership, TeamRole

User = get_user_model()


def update_search_vector(note_id: str) -> None:
    """Update PostgreSQL search vector for a note."""
    Note.all_objects.filter(id=note_id).update(
        search_vector=(
            SearchVector("title", weight="A", config="english")
            + SearchVector("body", weight="B", config="english")
        )
    )


@transaction.atomic
def note_create(
    *,
    author: User,
    title: str,
    body: str = "",
    team: Team | None = None,
    tags: Iterable[Tag] | None = None,
    visibility: str = NoteVisibility.TEAM,
    is_pinned: bool = False,
) -> Note:
    """Create a note with initial version snapshot and search indexing."""
    if team is not None:
        membership = TeamMembership.objects.filter(team=team, user=author).first()
        if not membership:
            raise PermissionDeniedError("You are not a member of this team.")
        if membership.role == TeamRole.VIEWER:
            raise PermissionDeniedError("Viewers cannot create notes.")
    else:
        # Personal note is always private to author
        visibility = NoteVisibility.PRIVATE

    note = Note.objects.create(
        author=author,
        team=team,
        title=title,
        body=body,
        visibility=visibility,
        is_pinned=is_pinned,
        version=1,
    )

    if tags:
        note.tags.set(tags)

    NoteVersion.objects.create(
        note=note,
        version_number=1,
        title=title,
        body=body,
        edited_by=author,
        change_summary="Initial creation",
    )

    update_search_vector(note.id)
    return note


@transaction.atomic
def note_update(
    *,
    note: Note,
    expected_version: int,
    user: User,
    title: str | None = None,
    body: str | None = None,
    tags: Iterable[Tag] | None = None,
    visibility: str | None = None,
    is_pinned: bool | None = None,
    change_summary: str = "",
) -> Note:
    """Update note using Optimistic Concurrency Control (OCC)."""
    # Refetch fresh note to check version conflict
    fresh_note = Note.objects.select_for_update().filter(id=note.id).first()
    if not fresh_note:
        raise ValidationError("Note no longer exists.")

    if fresh_note.version != expected_version:
        raise ConflictError(
            f"Conflict: Note is currently at version {fresh_note.version}, "
            f"but your edit was based on version {expected_version}."
        )

    # Apply updates
    if title is not None:
        fresh_note.title = title
    if body is not None:
        fresh_note.body = body
    if visibility is not None:
        fresh_note.visibility = visibility
    if is_pinned is not None:
        fresh_note.is_pinned = is_pinned

    fresh_note.version = fresh_note.version + 1
    fresh_note.save()

    if tags is not None:
        fresh_note.tags.set(tags)

    # Snapshot history
    NoteVersion.objects.create(
        note=fresh_note,
        version_number=fresh_note.version,
        title=fresh_note.title,
        body=fresh_note.body,
        edited_by=user,
        change_summary=change_summary or f"Updated to version {fresh_note.version}",
    )

    update_search_vector(fresh_note.id)
    return fresh_note


@transaction.atomic
def note_revert(*, note: Note, version_number: int, user: User) -> Note:
    """Revert note content to a historical revision."""
    historical = NoteVersion.objects.filter(note=note, version_number=version_number).first()
    if not historical:
        raise ValidationError(f"Revision version {version_number} does not exist for this note.")

    fresh_note = Note.objects.filter(id=note.id).first()
    if not fresh_note:
        raise ValidationError("Note no longer exists.")

    return note_update(
        note=fresh_note,
        expected_version=fresh_note.version,
        user=user,
        title=historical.title,
        body=historical.body,
        change_summary=f"Reverted to revision {version_number}",
    )


@transaction.atomic
def note_share_to_team(
    *, note: Note, team: Team, user: User, visibility: str = NoteVisibility.TEAM
) -> Note:
    """Promote/share a personal note to a team workspace."""
    if note.team is not None:
        raise ValidationError("This note is already assigned to a team.")

    if note.author_id != user.id:
        raise PermissionDeniedError("Only the author can share a personal note.")

    membership = TeamMembership.objects.filter(team=team, user=user).first()
    if not membership:
        raise PermissionDeniedError("You are not a member of the target team.")
    if membership.role == TeamRole.VIEWER:
        raise PermissionDeniedError("Viewers cannot share notes to the team.")

    note.team = team
    note.visibility = visibility
    note.version = note.version + 1
    note.save()

    NoteVersion.objects.create(
        note=note,
        version_number=note.version,
        title=note.title,
        body=note.body,
        edited_by=user,
        change_summary=f"Shared note to team '{team.name}'",
    )

    update_search_vector(note.id)
    return note
