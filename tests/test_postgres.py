import os
from uuid import uuid4

import pytest
from app import create_app


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='PostgreSQL integration runs in GitHub Actions')
def test_postgres_survives_application_replacement():
    config = {'TESTING': True, 'APP_ENV': 'production', 'STORAGE_BACKEND': 'database',
              'DATABASE_URL': os.environ['TEST_DATABASE_URL']}
    first = create_app(config)
    title = 'PostgreSQL persistence ' + uuid4().hex
    with first.test_client() as client:
        response = client.post('/api/requests', json={
            'title': title, 'category': 'software', 'priority': 'low'})
        assert response.status_code == 201
        item = response.json
    first.extensions['request_store'].engine.dispose()
    second = create_app(config)
    with second.test_client() as client:
        assert client.get('/health').status_code == 200
        response = client.get(f"/api/requests/{item['id']}")
        assert response.json == item
        assert item in client.get('/api/requests').json
    second.extensions['request_store'].engine.dispose()
