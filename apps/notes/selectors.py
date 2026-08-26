"""Selectors for querying notes, tags, and full-text search with tenant scoping."""

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Q, QuerySet

from apps.notes.models import Note, NoteVisibility, Tag
from apps.teams.models import TeamMembership, TeamRole

User = get_user_model()


def get_accessible_notes_base_queryset(
    user: User, *, include_deleted: bool = False
) -> QuerySet[Note]:
    """Return base queryset of all notes accessible by user (personal + team notes)."""
    if not user.is_authenticated:
        return Note.objects.none()

    manager = Note.all_objects if include_deleted else Note.objects

    # User's memberships
    memberships = TeamMembership.objects.filter(user=user)
    team_ids = memberships.values_list("team_id", flat=True)
    admin_team_ids = memberships.filter(role__in=[TeamRole.OWNER, TeamRole.ADMIN]).values_list(
        "team_id", flat=True
    )

    # Scoping conditions:
    # 1. Personal notes owned by user
    personal_condition = Q(author=user, team__isnull=True)

    # 2. Team notes with TEAM visibility in user's teams
    team_public_condition = Q(team_id__in=team_ids, visibility=NoteVisibility.TEAM)

    # 3. Team notes with PRIVATE visibility authored by user
    team_private_own_condition = Q(
        team_id__in=team_ids, visibility=NoteVisibility.PRIVATE, author=user
    )

    # 4. Team notes with PRIVATE visibility where user is OWNER/ADMIN
    team_private_admin_condition = Q(team_id__in=admin_team_ids, visibility=NoteVisibility.PRIVATE)

    qs = (
        manager.filter(
            personal_condition
            | team_public_condition
            | team_private_own_condition
            | team_private_admin_condition
        )
        .select_related("author", "team")
        .prefetch_related("tags")
    )

    if include_deleted:
        qs = qs.filter(deleted_at__isnull=False)
    else:
        qs = qs.filter(deleted_at__isnull=True)

    return qs.distinct()


def note_list_for_user(
    user: User,
    *,
    team_id: str | None = None,
    personal_only: bool = False,
    tag_id: str | None = None,
    is_pinned: bool | None = None,
    include_deleted: bool = False,
) -> QuerySet[Note]:
    """Retrieve filtered list of notes accessible to the user."""
    qs = get_accessible_notes_base_queryset(user, include_deleted=include_deleted)

    if personal_only:
        qs = qs.filter(team__isnull=True)
    elif team_id:
        qs = qs.filter(team_id=team_id)

    if tag_id:
        qs = qs.filter(tags__id=tag_id)

    if is_pinned is not None:
        qs = qs.filter(is_pinned=is_pinned)

    return qs


def note_search_for_user(
    user: User,
    *,
    query: str,
    team_id: str | None = None,
    personal_only: bool = False,
) -> QuerySet[Note]:
    """Execute PostgreSQL ranked full-text search across accessible notes."""
    qs = get_accessible_notes_base_queryset(user, include_deleted=False)

    if personal_only:
        qs = qs.filter(team__isnull=True)
    elif team_id:
        qs = qs.filter(team_id=team_id)

    if not query.strip():
        return qs

    search_query = SearchQuery(query, config="english", search_type="websearch")
    qs = (
        qs.filter(search_vector=search_query)
        .annotate(rank=SearchRank("search_vector", search_query))
        .order_by("-rank", "-updated_at")
    )

    # Fallback to icontains if search_vector returns nothing (e.g. partial substring)
    if not qs.exists():
        qs = get_accessible_notes_base_queryset(user, include_deleted=False).filter(
            Q(title__icontains=query) | Q(body__icontains=query)
        )
        if personal_only:
            qs = qs.filter(team__isnull=True)
        elif team_id:
            qs = qs.filter(team_id=team_id)

    return qs


def get_tags_for_user(user: User, *, team_id: str | None = None) -> QuerySet[Tag]:
    """Return tags accessible to user."""
    if not user.is_authenticated:
        return Tag.objects.none()

    if team_id:
        # Check membership
        if not TeamMembership.objects.filter(team_id=team_id, user=user).exists():
            return Tag.objects.none()
        return Tag.objects.filter(team_id=team_id)

    team_ids = TeamMembership.objects.filter(user=user).values_list("team_id", flat=True)
    return Tag.objects.filter(
        Q(team__isnull=True, created_by=user) | Q(team_id__in=team_ids)
    ).distinct()
