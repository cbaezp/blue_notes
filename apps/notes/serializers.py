"""Serializers for Notes, Tags, and Note Versions."""

from rest_framework import serializers

from apps.notes.models import Note, NoteVersion, NoteVisibility, Tag
from apps.teams.models import Team
from apps.users.serializers import UserSerializer


class TagSerializer(serializers.ModelSerializer):
    """Serializer for categorical note tags."""

    class Meta:
        model = Tag
        fields = ["id", "name", "color", "team", "created_at"]
        read_only_fields = ["id", "created_at"]


class TagCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tags."""

    class Meta:
        model = Tag
        fields = ["name", "color", "team"]


class NoteVersionSerializer(serializers.ModelSerializer):
    """Serializer for historical note revision snapshots."""

    edited_by = UserSerializer(read_only=True)

    class Meta:
        model = NoteVersion
        fields = [
            "id",
            "version_number",
            "title",
            "body",
            "edited_by",
            "change_summary",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "version_number",
            "title",
            "body",
            "edited_by",
            "change_summary",
            "created_at",
        ]


class NoteListSerializer(serializers.ModelSerializer):
    """Compact serializer for note listing and search results."""

    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True, default=None)
    snippet = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            "id",
            "title",
            "snippet",
            "team",
            "team_name",
            "author",
            "visibility",
            "version",
            "is_pinned",
            "is_personal",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_snippet(self, obj: Note) -> str:
        if not obj.body:
            return ""
        return obj.body[:150] + ("..." if len(obj.body) > 150 else "")


class NoteDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer for a note including complete body and history."""

    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True, default=None)

    class Meta:
        model = Note
        fields = [
            "id",
            "title",
            "body",
            "team",
            "team_name",
            "author",
            "visibility",
            "version",
            "is_pinned",
            "is_personal",
            "tags",
            "created_at",
            "updated_at",
            "deleted_at",
        ]
        read_only_fields = fields


class NoteCreateSerializer(serializers.Serializer):
    """Input serializer for creating a new note (personal or team)."""

    title = serializers.CharField(max_length=255, required=True)
    body = serializers.CharField(required=False, allow_blank=True, default="")
    team_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    visibility = serializers.ChoiceField(
        choices=NoteVisibility.choices, default=NoteVisibility.TEAM
    )
    is_pinned = serializers.BooleanField(default=False)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    def validate_team_id(self, value: str | None) -> Team | None:
        if value is None:
            return None
        team = Team.objects.filter(id=value).first()
        if not team:
            raise serializers.ValidationError("Team with this ID does not exist.")
        return team


class NoteUpdateSerializer(serializers.Serializer):
    """Input serializer for updating a note with Optimistic Concurrency Control."""

    title = serializers.CharField(max_length=255, required=False)
    body = serializers.CharField(required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=NoteVisibility.choices, required=False)
    is_pinned = serializers.BooleanField(required=False)
    expected_version = serializers.IntegerField(
        required=True,
        help_text="The version of the note you are editing. Used to prevent lost updates.",
    )
    change_summary = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
    )


class NoteRevertSerializer(serializers.Serializer):
    """Input serializer for reverting a note to a prior version."""

    version_number = serializers.IntegerField(required=True, min_value=1)


class ShareNoteToTeamSerializer(serializers.Serializer):
    """Input serializer for sharing/promoting a personal note to a team workspace."""

    team_id = serializers.UUIDField(required=True)
    visibility = serializers.ChoiceField(
        choices=NoteVisibility.choices, default=NoteVisibility.TEAM
    )

    def validate_team_id(self, value: str) -> Team:
        team = Team.objects.filter(id=value).first()
        if not team:
            raise serializers.ValidationError("Team with this ID does not exist.")
        return team
