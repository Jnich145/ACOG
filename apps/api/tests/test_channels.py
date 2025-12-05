"""
Tests for channel CRUD endpoints.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestChannelEndpoints:
    """Tests for channel API endpoints."""

    def test_create_channel_success(
        self,
        client: TestClient,
        sample_channel_data: dict[str, Any],
    ) -> None:
        """Creating a channel should return 201 with channel data."""
        response = client.post("/api/v1/channels", json=sample_channel_data)
        assert response.status_code == 201

        data = response.json()
        assert "data" in data
        assert data["data"]["name"] == sample_channel_data["name"]
        assert "id" in data["data"]

    def test_create_channel_missing_required_fields(
        self,
        client: TestClient,
    ) -> None:
        """Creating a channel without required fields should fail."""
        response = client.post("/api/v1/channels", json={"name": "Test"})
        assert response.status_code == 422  # Validation error

    def test_list_channels_empty(self, client: TestClient) -> None:
        """Listing channels when none exist should return empty list."""
        response = client.get("/api/v1/channels")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_list_channels_with_data(
        self,
        client: TestClient,
        created_channel: Any,
    ) -> None:
        """Listing channels should include created channels."""
        response = client.get("/api/v1/channels")
        assert response.status_code == 200

        data = response.json()
        assert len(data["data"]) >= 1

    def test_get_channel_by_id(
        self,
        client: TestClient,
        created_channel: Any,
    ) -> None:
        """Getting a channel by ID should return the channel."""
        response = client.get(f"/api/v1/channels/{created_channel.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["id"] == str(created_channel.id)

    def test_get_channel_not_found(self, client: TestClient) -> None:
        """Getting a non-existent channel should return 404."""
        fake_id = uuid4()
        response = client.get(f"/api/v1/channels/{fake_id}")
        assert response.status_code == 404

    def test_update_channel(
        self,
        client: TestClient,
        created_channel: Any,
    ) -> None:
        """Updating a channel should return updated data."""
        update_data = {"name": "Updated Channel Name"}
        response = client.put(
            f"/api/v1/channels/{created_channel.id}",
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["name"] == "Updated Channel Name"

    def test_delete_channel(
        self,
        client: TestClient,
        sample_channel_data: dict[str, Any],
    ) -> None:
        """Deleting a channel should soft delete it."""
        # First create a channel
        create_response = client.post("/api/v1/channels", json=sample_channel_data)
        channel_id = create_response.json()["data"]["id"]

        # Then delete it
        delete_response = client.delete(f"/api/v1/channels/{channel_id}")
        assert delete_response.status_code == 200

        # Verify it's not returned in list
        list_response = client.get("/api/v1/channels")
        channel_ids = [c["id"] for c in list_response.json()["data"]]
        assert channel_id not in channel_ids
