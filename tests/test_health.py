def test_health_reports_ok_and_mock_providers(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database_ok"] is True
    assert "music:mock" in body["providers"]
    assert "mock_generation" in body["job_types"]


def test_root(client):
    assert client.get("/").json()["name"] == "SR Generator"
