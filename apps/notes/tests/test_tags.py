"""Integration tests for Tag categorization and constraints."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import TagFactory, TeamFactory, UserFactory


@pytest.mark.django_db
class TestTagsAPI:
    """Test suite for Tag management and multi-tenant scoping."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.other_user = UserFactory()
        # TeamFactory automatically creates owner membership for created_by
        self.team = TeamFactory(created_by=self.user)

    def test_create_personal_tag(self):
        """Verify creating a personal tag."""
        self.client.force_authenticate(user=self.user)
        url = reverse("notes:tags-list")
        payload = {"name": "Personal Ideas", "color": "#10B981", "team": None}
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Personal Ideas"
        assert response.data["team"] is None

    def test_create_team_tag(self):
        """Verify creating a team tag."""
        self.client.force_authenticate(user=self.user)
        url = reverse("notes:tags-list")
        payload = {"name": "Sprint 42", "color": "#EF4444", "team": str(self.team.id)}
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["team"] == self.team.id

    def test_list_tags_scoped_to_user(self):
        """Verify tags are scoped to user's personal tags and member teams."""
        TagFactory(name="My Tag", created_by=self.user, team=None)
        TagFactory(name="Other User Tag", created_by=self.other_user, team=None)

        self.client.force_authenticate(user=self.user)
        url = reverse("notes:tags-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        tag_names = [t["name"] for t in response.data["results"]]
        assert "My Tag" in tag_names
        assert "Other User Tag" not in tag_names
