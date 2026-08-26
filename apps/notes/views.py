"""Views and ViewSets for Notes and Tags."""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.pagination import StandardResultsSetPagination
from apps.notes.models import NoteVersion
from apps.notes.permissions import CanDeleteNote, CanEditNote, CanViewNote
from apps.notes.selectors import (
    get_accessible_notes_base_queryset,
    get_tags_for_user,
    note_list_for_user,
    note_search_for_user,
)
from apps.notes.serializers import (
    NoteCreateSerializer,
    NoteDetailSerializer,
    NoteListSerializer,
    NoteRevertSerializer,
    NoteUpdateSerializer,
    NoteVersionSerializer,
    ShareNoteToTeamSerializer,
    TagCreateSerializer,
    TagSerializer,
)
from apps.notes.services import (
    note_create,
    note_revert,
    note_share_to_team,
    note_update,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Notes"],
        summary="List accessible notes",
        description="Returns a paginated list of notes accessible to the user (personal notes and shared team notes).",
        parameters=[
            OpenApiParameter(
                "team", str, location=OpenApiParameter.QUERY, description="Filter by team UUID"
            ),
            OpenApiParameter(
                "personal",
                bool,
                location=OpenApiParameter.QUERY,
                description="Filter personal notes only (true/false)",
            ),
            OpenApiParameter(
                "tag", str, location=OpenApiParameter.QUERY, description="Filter by tag UUID"
            ),
            OpenApiParameter(
                "is_pinned",
                bool,
                location=OpenApiParameter.QUERY,
                description="Filter by pinned status (true/false)",
            ),
            OpenApiParameter(
                "page", int, location=OpenApiParameter.QUERY, description="Page number"
            ),
            OpenApiParameter(
                "page_size", int, location=OpenApiParameter.QUERY, description="Results per page"
            ),
        ],
        responses={status.HTTP_200_OK: NoteListSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Notes"],
        summary="Create a note",
        description="Creates a new note. Set team_id to null for a personal note, or specify a team UUID for a team note.",
        request=NoteCreateSerializer,
        responses={status.HTTP_201_CREATED: NoteDetailSerializer},
    ),
    retrieve=extend_schema(
        tags=["Notes"],
        summary="Get note details",
        description="Retrieves full content, tags, version, and metadata for a specific note.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID")
        ],
        responses={status.HTTP_200_OK: NoteDetailSerializer},
    ),
    update=extend_schema(
        tags=["Notes"],
        summary="Update note (with OCC)",
        description="Updates note content. Requires `expected_version` to prevent lost updates via Optimistic Concurrency Control.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID")
        ],
        request=NoteUpdateSerializer,
        responses={
            status.HTTP_200_OK: NoteDetailSerializer,
            status.HTTP_409_CONFLICT: "Version conflict: Note was modified by another request.",
        },
    ),
    partial_update=extend_schema(
        tags=["Notes"],
        summary="Partial update note (with OCC)",
        description="Partially updates note fields. Requires `expected_version`.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID")
        ],
        request=NoteUpdateSerializer,
        responses={
            status.HTTP_200_OK: NoteDetailSerializer,
            status.HTTP_409_CONFLICT: "Version conflict",
        },
    ),
    destroy=extend_schema(
        tags=["Notes"],
        summary="Delete note (Soft delete / Hard delete)",
        description="Moves note to trash by default. Pass `?hard=true` to permanently delete.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID"),
            OpenApiParameter(
                "hard",
                bool,
                location=OpenApiParameter.QUERY,
                description="Pass true to permanently delete instead of soft-deleting to trash.",
            ),
        ],
        responses={status.HTTP_204_NO_CONTENT: None},
    ),
)
class NoteViewSet(viewsets.GenericViewSet):
    """Manage personal and team notes, search, revisions, and concurrency."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        include_deleted = self.action in ["trash", "restore"]
        return get_accessible_notes_base_queryset(
            self.request.user, include_deleted=include_deleted
        )

    def get_serializer_class(self):
        if self.action in ["list", "search", "trash"]:
            return NoteListSerializer
        if self.action == "create":
            return NoteCreateSerializer
        if self.action in ["update", "partial_update"]:
            return NoteUpdateSerializer
        if self.action == "history":
            return NoteVersionSerializer
        if self.action == "revert":
            return NoteRevertSerializer
        if self.action == "share_to_team":
            return ShareNoteToTeamSerializer
        return NoteDetailSerializer

    def get_permissions(self):
        if self.action in ["update", "partial_update", "revert"]:
            return [permissions.IsAuthenticated(), CanEditNote()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), CanDeleteNote()]
        if self.action in ["retrieve", "history"]:
            return [permissions.IsAuthenticated(), CanViewNote()]
        return [permissions.IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        team_id = request.query_params.get("team")
        personal_param = request.query_params.get("personal")
        personal_only = personal_param is not None and personal_param.lower() in [
            "true",
            "1",
            "yes",
        ]
        tag_id = request.query_params.get("tag")
        is_pinned_param = request.query_params.get("is_pinned")
        is_pinned = is_pinned_param.lower() in ["true", "1"] if is_pinned_param else None

        qs = note_list_for_user(
            user=request.user,
            team_id=team_id,
            personal_only=personal_only,
            tag_id=tag_id,
            is_pinned=is_pinned,
            include_deleted=False,
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = NoteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = NoteListSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = NoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tag_ids = serializer.validated_data.get("tag_ids", [])
        from apps.notes.models import Tag

        tags = Tag.objects.filter(id__in=tag_ids) if tag_ids else None

        note = note_create(
            author=request.user,
            title=serializer.validated_data["title"],
            body=serializer.validated_data.get("body", ""),
            team=serializer.validated_data.get("team_id"),
            tags=tags,
            visibility=serializer.validated_data.get("visibility"),
            is_pinned=serializer.validated_data.get("is_pinned", False),
        )

        return Response(NoteDetailSerializer(note).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        note = self.get_object()
        serializer = NoteDetailSerializer(note)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        note = self.get_object()
        serializer = NoteUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tag_ids = serializer.validated_data.get("tag_ids")
        from apps.notes.models import Tag

        tags = Tag.objects.filter(id__in=tag_ids) if tag_ids is not None else None

        expected_version = serializer.validated_data.get("expected_version")

        updated_note = note_update(
            note=note,
            expected_version=expected_version,
            user=request.user,
            title=serializer.validated_data.get("title"),
            body=serializer.validated_data.get("body"),
            tags=tags,
            visibility=serializer.validated_data.get("visibility"),
            is_pinned=serializer.validated_data.get("is_pinned"),
            change_summary=serializer.validated_data.get("change_summary", ""),
        )

        return Response(NoteDetailSerializer(updated_note).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        note = self.get_object()
        hard_delete = request.query_params.get("hard", "").lower() in ["true", "1"]
        if hard_delete:
            note.delete()
        else:
            note.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Notes"],
        summary="Restore note from trash",
        description="Restores a previously soft-deleted note back to active status.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID")
        ],
        responses={status.HTTP_200_OK: NoteDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        note = self.get_object()
        note.restore()
        return Response(NoteDetailSerializer(note).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Notes"],
        summary="Get revision history",
        description="Returns chronological audit snapshots of all past edits made to this note.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID")
        ],
        responses={status.HTTP_200_OK: NoteVersionSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        note = self.get_object()
        history_qs = (
            NoteVersion.objects.filter(note=note)
            .select_related("edited_by")
            .order_by("-version_number")
        )
        serializer = NoteVersionSerializer(history_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Notes"],
        summary="Revert note to historical version",
        description="Restores title and body from a prior version number as a new version.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID")
        ],
        request=NoteRevertSerializer,
        responses={status.HTTP_200_OK: NoteDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="revert")
    def revert(self, request, pk=None):
        note = self.get_object()
        serializer = NoteRevertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reverted_note = note_revert(
            note=note,
            version_number=serializer.validated_data["version_number"],
            user=request.user,
        )
        return Response(NoteDetailSerializer(reverted_note).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Notes"],
        summary="Share personal note to team workspace",
        description="Promotes a personal note (`team=null`) into a team workspace.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Note UUID")
        ],
        request=ShareNoteToTeamSerializer,
        responses={status.HTTP_200_OK: NoteDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="share-to-team")
    def share_to_team(self, request, pk=None):
        note = self.get_object()
        serializer = ShareNoteToTeamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shared_note = note_share_to_team(
            note=note,
            team=serializer.validated_data["team_id"],
            user=request.user,
            visibility=serializer.validated_data.get("visibility"),
        )
        return Response(NoteDetailSerializer(shared_note).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Notes"],
        summary="Ranked Full-Text Search across notes",
        description="Executes PostgreSQL ranked full-text search against title and body with tenant scoping.",
        parameters=[
            OpenApiParameter(
                "q",
                str,
                required=True,
                location=OpenApiParameter.QUERY,
                description="Search term or phrase",
            ),
            OpenApiParameter(
                "team",
                str,
                location=OpenApiParameter.QUERY,
                description="Filter search by team UUID",
            ),
            OpenApiParameter(
                "personal",
                bool,
                location=OpenApiParameter.QUERY,
                description="Search personal notes only",
            ),
            OpenApiParameter(
                "page", int, location=OpenApiParameter.QUERY, description="Page number"
            ),
            OpenApiParameter(
                "page_size", int, location=OpenApiParameter.QUERY, description="Results per page"
            ),
        ],
        responses={status.HTTP_200_OK: NoteListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        query = request.query_params.get("q", "")
        team_id = request.query_params.get("team")
        personal_param = request.query_params.get("personal")
        personal_only = personal_param is not None and personal_param.lower() in [
            "true",
            "1",
            "yes",
        ]

        qs = note_search_for_user(
            user=request.user,
            query=query,
            team_id=team_id,
            personal_only=personal_only,
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = NoteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = NoteListSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Notes"],
        summary="List soft-deleted notes in trash",
        description="Returns list of notes currently in trash that can be restored.",
        parameters=[
            OpenApiParameter(
                "page", int, location=OpenApiParameter.QUERY, description="Page number"
            ),
            OpenApiParameter(
                "page_size", int, location=OpenApiParameter.QUERY, description="Results per page"
            ),
        ],
        responses={status.HTTP_200_OK: NoteListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="trash")
    def trash(self, request):
        qs = note_list_for_user(user=request.user, include_deleted=True)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = NoteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = NoteListSerializer(qs, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=["Tags"],
        summary="List accessible tags",
        description="Returns tags created by the user or available in the specified team workspace.",
        parameters=[
            OpenApiParameter(
                "team", str, location=OpenApiParameter.QUERY, description="Filter tags by team UUID"
            ),
            OpenApiParameter(
                "page", int, location=OpenApiParameter.QUERY, description="Page number"
            ),
            OpenApiParameter(
                "page_size", int, location=OpenApiParameter.QUERY, description="Results per page"
            ),
        ],
        responses={status.HTTP_200_OK: TagSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Tags"],
        summary="Create a tag",
        description="Creates a tag. Set team to null for a personal tag, or specify a team UUID.",
        request=TagCreateSerializer,
        responses={status.HTTP_201_CREATED: TagSerializer},
    ),
    retrieve=extend_schema(
        tags=["Tags"],
        summary="Get tag details",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Tag UUID")
        ],
        responses={status.HTTP_200_OK: TagSerializer},
    ),
    update=extend_schema(
        tags=["Tags"],
        summary="Replace tag",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Tag UUID")
        ],
        request=TagCreateSerializer,
        responses={status.HTTP_200_OK: TagSerializer},
    ),
    partial_update=extend_schema(
        tags=["Tags"],
        summary="Update tag",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Tag UUID")
        ],
        request=TagCreateSerializer,
        responses={status.HTTP_200_OK: TagSerializer},
    ),
    destroy=extend_schema(
        tags=["Tags"],
        summary="Delete a tag",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Tag UUID")
        ],
        responses={status.HTTP_204_NO_CONTENT: None},
    ),
)
class TagViewSet(viewsets.ModelViewSet):
    """Manage tags for notes categorization."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TagSerializer

    def get_queryset(self):
        team_id = self.request.query_params.get("team")
        return get_tags_for_user(self.request.user, team_id=team_id)

    def get_serializer_class(self):
        if self.action == "create":
            return TagCreateSerializer
        return TagSerializer

    def create(self, request, *args, **kwargs):
        serializer = TagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = serializer.save(created_by=request.user)
        return Response(TagSerializer(tag).data, status=status.HTTP_201_CREATED)
