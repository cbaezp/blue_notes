"""ViewSets and actions for Teams and TeamMembers."""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.pagination import StandardResultsSetPagination
from apps.teams.permissions import IsTeamAdminOrOwner, IsTeamMember, IsTeamOwner
from apps.teams.selectors import get_team_members, get_teams_for_user
from apps.teams.serializers import (
    AddMemberSerializer,
    TeamCreateUpdateSerializer,
    TeamMembershipSerializer,
    TeamSerializer,
    UpdateMemberRoleSerializer,
)
from apps.teams.services import (
    team_add_member,
    team_create,
    team_remove_member,
    team_update_member_role,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Teams"],
        summary="List all teams",
        description="Returns a paginated list of all team workspaces the current user is a member of.",
        responses={status.HTTP_200_OK: TeamSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["Teams"],
        summary="Create team workspace",
        description="Creates a new team workspace and automatically assigns the creator as OWNER.",
        request=TeamCreateUpdateSerializer,
        responses={status.HTTP_201_CREATED: TeamSerializer},
    ),
    retrieve=extend_schema(
        tags=["Teams"],
        summary="Get team workspace details",
        description="Retrieves metadata and current user's role in the specified team workspace.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID")
        ],
        responses={status.HTTP_200_OK: TeamSerializer},
    ),
    update=extend_schema(
        tags=["Teams"],
        summary="Replace team details",
        description="Requires OWNER or ADMIN role. Updates the team's name and description.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID")
        ],
        request=TeamCreateUpdateSerializer,
        responses={status.HTTP_200_OK: TeamSerializer},
    ),
    partial_update=extend_schema(
        tags=["Teams"],
        summary="Update team details",
        description="Requires OWNER or ADMIN role. Partially updates team name or description.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID")
        ],
        request=TeamCreateUpdateSerializer,
        responses={status.HTTP_200_OK: TeamSerializer},
    ),
    destroy=extend_schema(
        tags=["Teams"],
        summary="Delete team workspace",
        description="Requires OWNER role. Permanently deletes the team workspace and its memberships.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID")
        ],
        responses={status.HTTP_204_NO_CONTENT: None},
    ),
)
class TeamViewSet(viewsets.ModelViewSet):
    """ViewSet for managing team workspaces and member rosters."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return get_teams_for_user(self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return TeamCreateUpdateSerializer
        return TeamSerializer

    def get_permissions(self):
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), IsTeamAdminOrOwner()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsTeamOwner()]
        if self.action in [
            "retrieve",
            "members",
            "add_member",
            "update_member_role",
            "remove_member",
        ]:
            return [permissions.IsAuthenticated(), IsTeamMember()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = team_create(
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            created_by=request.user,
        )
        return Response(
            TeamSerializer(team, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Teams"],
        summary="List team members",
        description="Lists all users and their respective roles within the team.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID")
        ],
        responses={status.HTTP_200_OK: TeamMembershipSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        team = self.get_object()
        memberships = get_team_members(team)
        serializer = TeamMembershipSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Teams"],
        summary="Add / Invite member to team",
        description="Requires OWNER or ADMIN role. Adds an existing user into the team with a specified role.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID")
        ],
        request=AddMemberSerializer,
        responses={status.HTTP_201_CREATED: TeamMembershipSerializer},
    )
    @action(detail=True, methods=["post"], url_path="members/add")
    def add_member(self, request, pk=None):
        team = self.get_object()
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership = team_add_member(
            team=team,
            user=serializer.validated_data["user_id"],
            role=serializer.validated_data["role"],
            acting_user=request.user,
        )
        return Response(TeamMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Teams"],
        summary="Update member role",
        description="Requires OWNER or ADMIN role. Updates a member's role (OWNER, ADMIN, MEMBER, VIEWER).",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID"),
            OpenApiParameter("user_id", int, location=OpenApiParameter.PATH, description="User ID"),
        ],
        request=UpdateMemberRoleSerializer,
        responses={status.HTTP_200_OK: TeamMembershipSerializer},
    )
    @action(detail=True, methods=["patch"], url_path=r"members/(?P<user_id>[^/.]+)/role")
    def update_member_role(self, request, pk=None, user_id=None):
        team = self.get_object()
        serializer = UpdateMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from django.contrib.auth import get_user_model

        user = get_user_model().objects.filter(id=user_id).first()
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        membership = team_update_member_role(
            team=team,
            target_user=user,
            new_role=serializer.validated_data["role"],
            acting_user=request.user,
        )
        return Response(TeamMembershipSerializer(membership).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Teams"],
        summary="Remove member or leave team",
        description="Admins/Owners can remove members. Any member can remove themselves to leave the team. The sole owner cannot be removed.",
        parameters=[
            OpenApiParameter("id", str, location=OpenApiParameter.PATH, description="Team UUID"),
            OpenApiParameter("user_id", int, location=OpenApiParameter.PATH, description="User ID"),
        ],
        responses={status.HTTP_204_NO_CONTENT: None},
    )
    @action(detail=True, methods=["delete"], url_path=r"members/(?P<user_id>[^/.]+)")
    def remove_member(self, request, pk=None, user_id=None):
        team = self.get_object()
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.filter(id=user_id).first()
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        team_remove_member(team=team, target_user=user, acting_user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
