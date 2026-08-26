"""User authentication, registration, and profile views."""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import AuthTokenSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.GenericAPIView):
    """Register a new user account."""

    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Register a new user",
        description="Creates a new user account with validated credentials and returns the authentication token.",
        request=RegisterSerializer,
        responses={
            status.HTTP_201_CREATED: inline_serializer(
                name="RegisterSuccessResponse",
                fields={
                    "user": UserSerializer(),
                    "token": serializers.CharField(
                        help_text="Authentication token to use in headers"
                    ),
                },
            ),
            status.HTTP_400_BAD_REQUEST: inline_serializer(
                name="RegisterErrorResponse",
                fields={"error": serializers.DictField()},
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, token_key = serializer.save()
        user_data = UserSerializer(user).data
        return Response(
            {"user": user_data, "token": token_key},
            status=status.HTTP_201_CREATED,
        )


class ObtainAuthTokenView(APIView):
    """Authenticate with username and password to obtain an API token."""

    permission_classes = [permissions.AllowAny]
    serializer_class = AuthTokenSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Obtain auth token (Login)",
        description="Authenticates credentials and returns a persistent auth token.",
        request=AuthTokenSerializer,
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="AuthTokenSuccessResponse",
                fields={
                    "token": serializers.CharField(
                        help_text="API Token for Authorization: Token <key>"
                    ),
                    "user": UserSerializer(),
                },
            ),
            status.HTTP_400_BAD_REQUEST: inline_serializer(
                name="AuthTokenErrorResponse",
                fields={"error": serializers.DictField()},
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token_key = serializer.validated_data["token"]
        return Response(
            {"token": token_key, "user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """Retrieve or update current authenticated user's profile."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="Get current user profile",
        description="Returns profile details for the currently authenticated user.",
        responses={status.HTTP_200_OK: UserSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Authentication"],
        summary="Update current user profile",
        description="Update first_name, last_name, or email for the authenticated user.",
        request=UserSerializer,
        responses={status.HTTP_200_OK: UserSerializer},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        tags=["Authentication"],
        summary="Replace current user profile",
        description="Replace profile details for the authenticated user.",
        request=UserSerializer,
        responses={status.HTTP_200_OK: UserSerializer},
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    def get_object(self):
        return self.request.user


class LogoutView(generics.GenericAPIView):
    """Invalidate current user auth token."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.Serializer

    @extend_schema(
        tags=["Authentication"],
        summary="Logout / Revoke token",
        description="Deletes the current user's authentication token, ending the active session.",
        request=None,
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="LogoutResponse",
                fields={"message": serializers.CharField()},
            )
        },
    )
    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
