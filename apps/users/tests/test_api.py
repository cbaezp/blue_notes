"""Tests for User authentication, registration, and profile endpoints."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.mark.django_db
class TestUsersAPI:
    """Test suite for authentication workflows."""

    def setup_method(self):
        self.client = APIClient()

    def test_user_registration_success(self):
        """Verify successful user registration returns 201 with auth token and profile."""
        url = reverse("users:register")
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "token" in response.data
        assert response.data["user"]["username"] == "newuser"
        assert response.data["user"]["email"] == "newuser@example.com"

    def test_user_registration_password_mismatch(self):
        """Verify registration fails when password and confirmation differ."""
        url = reverse("users:register")
        payload = {
            "username": "mismatchuser",
            "email": "mismatch@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "DifferentPassword123!",
        }
        response = self.client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password_confirm" in response.data["error"]["details"]

    def test_obtain_auth_token_success(self):
        """Verify user can authenticate with username and password to retrieve token."""
        user = UserFactory(username="tokenuser", password="MySecretPassword123!")
        url = reverse("users:token")
        payload = {
            "username": "tokenuser",
            "password": "MySecretPassword123!",
        }
        response = self.client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert response.data["user"]["id"] == user.id

    def test_obtain_auth_token_invalid_credentials(self):
        """Verify authentication fails on incorrect password."""
        UserFactory(username="tokenuser", password="MySecretPassword123!")
        url = reverse("users:token")
        payload = {
            "username": "tokenuser",
            "password": "WrongPassword!",
        }
        response = self.client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_me_endpoint_authenticated(self):
        """Verify authenticated user can fetch their profile."""
        user = UserFactory()
        self.client.force_authenticate(user=user)
        url = reverse("users:me")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == user.id
        assert response.data["username"] == user.username

    def test_user_registration_duplicate_username_fails(self):
        """Verify registration with existing username returns 400."""
        UserFactory(username="existinguser")
        url = reverse("users:register")
        payload = {
            "username": "existinguser",
            "email": "another@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
        }
        response = self.client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_profile_update_authenticated(self):
        """Verify authenticated user can update their first_name, last_name, and email."""
        user = UserFactory(first_name="OldName")
        self.client.force_authenticate(user=user)
        url = reverse("users:me")
        payload = {"first_name": "UpdatedName", "last_name": "NewSurname"}
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "UpdatedName"
        assert response.data["last_name"] == "NewSurname"

    def test_logout_invalidates_token(self):
        """Verify logout revokes auth token and subsequent requests return 401."""
        UserFactory(username="logoutuser", password="Password123!")
        token_url = reverse("users:token")
        token_resp = self.client.post(
            token_url, {"username": "logoutuser", "password": "Password123!"}, format="json"
        )
        token = token_resp.data["token"]

        # Authenticate using token header
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        me_resp = self.client.get(reverse("users:me"))
        assert me_resp.status_code == status.HTTP_200_OK

        # Logout
        logout_resp = self.client.post(reverse("users:logout"))
        assert logout_resp.status_code == status.HTTP_200_OK

        # Try accessing /me/ again with revoked token
        revoked_resp = self.client.get(reverse("users:me"))
        assert revoked_resp.status_code == status.HTTP_401_UNAUTHORIZED
