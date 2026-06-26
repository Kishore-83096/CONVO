def test_base_url_redirects_to_complete_health_check(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/api/v1/health/all"
