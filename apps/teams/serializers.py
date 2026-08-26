"""Serializers for Team and TeamMembership resources."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.teams.models import Team, TeamMembership, TeamRole
from apps.users.serializers import UserSerializer

User = get_user_model()


class TeamMembershipSerializer(serializers.ModelSerializer):
    """Detailed serializer for team memberships including user profile."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "user", "role", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class TeamSerializer(serializers.ModelSerializer):
    """Serializer for Team entities including current user's membership role."""

    user_role = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "description",
            "created_at",
            "updated_at",
            "user_role",
            "members_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "user_role", "members_count"]

    def get_user_role(self, obj: Team) -> str | None:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            membership = TeamMembership.objects.filter(team=obj, user=request.user).first()
            return membership.role if membership else None
        return None

    def get_members_count(self, obj: Team) -> int:
        return obj.memberships.count()


class TeamCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating team records."""

    class Meta:
        model = Team
        fields = ["name", "description"]


class AddMemberSerializer(serializers.Serializer):
    """Input serializer for inviting/adding a user to a team."""

    user_id = serializers.IntegerField(required=True)
    role = serializers.ChoiceField(choices=TeamRole.choices, default=TeamRole.MEMBER)

    def validate_user_id(self, value: int) -> User:
        user = User.objects.filter(id=value).first()
        if not user:
            raise serializers.ValidationError("User with this ID does not exist.")
        return user


class UpdateMemberRoleSerializer(serializers.Serializer):
    """Input serializer for updating a member's role."""

    role = serializers.ChoiceField(choices=TeamRole.choices, required=True)
