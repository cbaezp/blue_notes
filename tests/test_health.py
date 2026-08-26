"""Test health check and basic environment setup."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_check(client):
    """Verify health endpoint responds with 200 and expected payload."""
    url = reverse("health_check")
    response = client.get(url)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "blue_notes"}
