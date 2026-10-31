from app import app

def test_release_health_contract():
    assert app.test_client().get('/health').status_code == 200
