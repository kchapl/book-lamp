def test_home_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Book Lamp" in resp.data
