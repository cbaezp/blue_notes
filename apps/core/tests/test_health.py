"""Core and health check tests."""

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_health_check(client):
    """Verify health endpoint responds with 200 and expected payload."""
    url = reverse("health_check")
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "service": "blue_notes"}
