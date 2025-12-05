"""
Tests for episode CRUD endpoints.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestEpisodeEndpoints:
    """Tests for episode API endpoints."""

    def test_create_episode_success(
        self,
        client: TestClient,
        created_channel: Any,
        sample_episode_data: dict[str, Any],
    ) -> None:
        """Creating an episode should return 201 with episode data."""
        response = client.post(
            "/api/v1/episodes",
            json=sample_episode_data,
            params={"channel_id": str(created_channel.id)},
        )
        assert response.status_code == 201

        data = response.json()
        assert "data" in data
        assert data["data"]["title"] == sample_episode_data["title"]
        assert data["data"]["status"] == "idea"

    def test_create_episode_invalid_channel(
        self,
        client: TestClient,
        sample_episode_data: dict[str, Any],
    ) -> None:
        """Creating an episode with invalid channel should fail."""
        fake_channel_id = uuid4()
        response = client.post(
            "/api/v1/episodes",
            json=sample_episode_data,
            params={"channel_id": str(fake_channel_id)},
        )
        assert response.status_code == 404

    def test_list_episodes_empty(self, client: TestClient) -> None:
        """Listing episodes when none exist should return empty list."""
        response = client.get("/api/v1/episodes")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_list_episodes_filter_by_channel(
        self,
        client: TestClient,
        created_channel: Any,
        created_episode: Any,
    ) -> None:
        """Listing episodes should filter by channel."""
        response = client.get(
            "/api/v1/episodes",
            params={"channel_id": str(created_channel.id)},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["data"]) >= 1
        assert all(e["channel_id"] == str(created_channel.id) for e in data["data"])

    def test_list_episodes_filter_by_status(
        self,
        client: TestClient,
        created_episode: Any,
    ) -> None:
        """Listing episodes should filter by status."""
        response = client.get("/api/v1/episodes", params={"status": "idea"})
        assert response.status_code == 200

    def test_get_episode_by_id(
        self,
        client: TestClient,
        created_episode: Any,
    ) -> None:
        """Getting an episode by ID should return the episode."""
        response = client.get(f"/api/v1/episodes/{created_episode.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["id"] == str(created_episode.id)

    def test_get_episode_not_found(self, client: TestClient) -> None:
        """Getting a non-existent episode should return 404."""
        fake_id = uuid4()
        response = client.get(f"/api/v1/episodes/{fake_id}")
        assert response.status_code == 404

    def test_update_episode(
        self,
        client: TestClient,
        created_episode: Any,
    ) -> None:
        """Updating an episode should return updated data."""
        update_data = {"title": "Updated Episode Title"}
        response = client.put(
            f"/api/v1/episodes/{created_episode.id}",
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["title"] == "Updated Episode Title"

    def test_delete_episode(
        self,
        client: TestClient,
        created_channel: Any,
        sample_episode_data: dict[str, Any],
    ) -> None:
        """Deleting an episode should soft delete it."""
        # First create an episode
        create_response = client.post(
            "/api/v1/episodes",
            json=sample_episode_data,
            params={"channel_id": str(created_channel.id)},
        )
        episode_id = create_response.json()["data"]["id"]

        # Then delete it
        delete_response = client.delete(f"/api/v1/episodes/{episode_id}")
        assert delete_response.status_code == 200

        # Verify it's not returned normally
        get_response = client.get(f"/api/v1/episodes/{episode_id}")
        assert get_response.status_code == 404

    def test_cancel_episode(
        self,
        client: TestClient,
        created_episode: Any,
    ) -> None:
        """Canceling an episode should change its status."""
        response = client.post(f"/api/v1/episodes/{created_episode.id}/cancel")
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["status"] == "cancelled"
