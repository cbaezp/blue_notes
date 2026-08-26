"""Tests for PostgreSQL Full-Text Search, Tag Filtering, and Multi-tenant Search Isolation."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.notes.services import note_create
from tests.factories import TagFactory, TeamFactory, UserFactory


@pytest.mark.django_db
class TestSearchAndFiltersAPI:
    """Test suite for full-text search, tag categorization, and tenant isolation."""

    def setup_method(self):
        self.client = APIClient()
        self.user_a = UserFactory(username="alice")
        self.user_b = UserFactory(username="bob")

        self.team_a = TeamFactory(name="Alpha Team", created_by=self.user_a)
        self.team_b = TeamFactory(name="Beta Team", created_by=self.user_b)

        # Create tags
        self.tag_backend = TagFactory(name="backend", team=self.team_a)
        self.tag_frontend = TagFactory(name="frontend", team=self.team_a)

        # Create notes in Team A
        self.note_django = note_create(
            author=self.user_a,
            title="Django REST Framework Best Practices",
            body="Optimizing database queries and serialization performance in Python.",
            team=self.team_a,
            tags=[self.tag_backend],
        )

        self.note_react = note_create(
            author=self.user_a,
            title="React Performance Tuning",
            body="Client-side caching and memoization patterns.",
            team=self.team_a,
            tags=[self.tag_frontend],
        )

        # Create confidential note in Team B (Alice is NOT a member)
        self.note_beta = note_create(
            author=self.user_b,
            title="Django Confidential Strategy in Beta",
            body="Secret algorithms for Python backend.",
            team=self.team_b,
        )

    def test_full_text_search_matching_query(self):
        """Verify searching for 'serialization' finds Django note."""
        self.client.force_authenticate(user=self.user_a)
        url = reverse("notes:notes-search")
        response = self.client.get(url, {"q": "serialization"})

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.note_django.id)

    def test_search_tenant_isolation(self):
        """Verify search query 'Django' only returns Team A notes for Alice, hiding Team B."""
        self.client.force_authenticate(user=self.user_a)
        url = reverse("notes:notes-search")
        response = self.client.get(url, {"q": "Django"})

        assert response.status_code == status.HTTP_200_OK
        result_ids = [n["id"] for n in response.data["results"]]
        assert str(self.note_django.id) in result_ids
        assert str(self.note_beta.id) not in result_ids  # Must be strictly hidden!

    def test_filter_by_tag(self):
        """Verify filtering notes by tag."""
        self.client.force_authenticate(user=self.user_a)
        url = reverse("notes:notes-list")
        response = self.client.get(url, {"tag": str(self.tag_backend.id)})

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.note_django.id)
