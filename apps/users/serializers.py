"""Serializers for user registration, authentication, and profile."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.authtoken.models import Token

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    """User registration serializer with password validation."""

    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data: dict) -> tuple[User, str]:
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        token, _ = Token.objects.get_or_create(user=user)
        return user, token.key


class AuthTokenSerializer(serializers.Serializer):
    """Serializer for authenticating with username/password and obtaining a token."""

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs: dict) -> dict:
        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"), username=username, password=password
        )
        if not user:
            raise serializers.ValidationError("Unable to authenticate with provided credentials.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        token, _ = Token.objects.get_or_create(user=user)
        attrs["user"] = user
        attrs["token"] = token.key
        return attrs
