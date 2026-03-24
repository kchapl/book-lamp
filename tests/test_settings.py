from book_lamp.app import get_storage
from book_lamp.services.mock_storage import MockStorage


def test_settings_storage():
    storage = MockStorage()

    # Test default
    settings = storage.get_settings()
    assert settings == {}

    # Update theme
    storage.update_setting("theme", "light")
    settings = storage.get_settings()
    assert settings.get("theme") == "light"

    # Overwrite theme
    storage.update_setting("theme", "dark")
    settings = storage.get_settings()
    assert settings.get("theme") == "dark"


def test_settings_api(authenticated_client):
    # authenticated_client already has mock storage and credentials
    storage = get_storage()

    # Update theme via API
    response = authenticated_client.post("/api/settings", json={"theme": "light"})
    assert response.status_code == 200
    assert response.json["success"] is True

    # Invalid theme
    response = authenticated_client.post("/api/settings", json={"theme": "invalid"})
    assert response.status_code == 200  # Should skip invalid but return success

    # Check if theme was updated (to the valid one)
    settings = storage.get_settings()
    assert settings.get("theme") == "light"

    # Update to system
    response = authenticated_client.post("/api/settings", json={"theme": "system"})
    assert response.status_code == 200
    settings = storage.get_settings()
    assert settings.get("theme") == "system"
