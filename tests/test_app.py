import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.exc import OperationalError

from app import create_app

VALID = {'title': 'Компьютерді тексеру', 'category': 'computer',
         'priority': 'medium', 'description': 'Жұмысын тексеру'}


@pytest.fixture(params=['memory', 'database'])
def application(request, tmp_path):
    return create_app({'TESTING': True, 'APP_ENV': 'test',
                       'STORAGE_BACKEND': request.param,
                       'DATABASE_URL': 'sqlite:///' + (tmp_path / 'test.db').as_posix()})


@pytest.fixture()
def client(application):
    with application.test_client() as test_client:
        yield test_client


def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'


def test_index(client):
    assert client.get('/').json['application'] == 'LabCloud'
    assert client.get('/').json['environment'] == 'test'


def test_create_request(client):
    response = client.post('/api/requests', json=VALID)
    assert response.status_code == 201
    assert response.json == dict(VALID, id=1)
    assert response.headers['Location'] == '/api/requests/1'


def test_reject_invalid_category(client):
    assert client.post('/api/requests', json=dict(VALID, category='unknown')).status_code == 400


def test_missing_request(client):
    assert client.get('/api/requests/999').status_code == 404


def test_reject_empty_title(client):
    assert client.post('/api/requests', json=dict(VALID, title='   ')).status_code == 400


def test_malformed_json(client):
    response = client.post('/api/requests', data='{"title":', content_type='application/json')
    assert response.status_code == 400
    assert 'error' in response.json


@pytest.mark.parametrize('body', [None, [], 'text', 12, True])
def test_requires_json_object(client, body):
    assert client.post('/api/requests', json=body).status_code == 400


@pytest.mark.parametrize('field,value', [
    ('title', 42), ('title', None), ('title', []),
    ('description', 42), ('description', None),
    ('category', []), ('category', {}), ('category', True),
    ('priority', []), ('priority', {}), ('priority', 1),
])
def test_wrong_field_type(client, field, value):
    assert client.post('/api/requests', json=dict(VALID, **{field: value})).status_code == 400


@pytest.mark.parametrize('field', ['title', 'category', 'priority'])
def test_missing_required_field(client, field):
    body = VALID.copy()
    body.pop(field)
    assert client.post('/api/requests', json=body).status_code == 400


@pytest.mark.parametrize('title_len,description_len,status', [
    (120, 1000, 201), (121, 1000, 400), (120, 1001, 400),
])
def test_text_length_boundaries(client, title_len, description_len, status):
    response = client.post('/api/requests', json=dict(
        VALID, title='т' * title_len, description='с' * description_len))
    assert response.status_code == status


def test_successful_readback(client):
    item = client.post('/api/requests', json=VALID).json
    response = client.get(f"/api/requests/{item['id']}")
    assert response.status_code == 200
    assert response.json == item
    assert client.get('/api/requests').json == [item]


def test_invalid_does_not_consume_id(client):
    client.post('/api/requests', json=dict(VALID, priority='urgent'))
    assert client.post('/api/requests', json=VALID).json['id'] == 1


def test_optional_description_and_trim(client):
    response = client.post('/api/requests', json={
        'title': '  Желіні тексеру  ', 'category': 'network', 'priority': 'high'})
    assert response.json['title'] == 'Желіні тексеру'
    assert response.json['description'] == ''


def test_empty_list(client):
    assert client.get('/api/requests').json == []


def test_oversized_body(client):
    assert client.post('/api/requests', data='x' * 20000,
                       content_type='application/json').status_code == 413


def test_json_route_errors(client):
    assert client.get('/missing').status_code == 404
    response = client.delete('/api/requests')
    assert response.status_code == 405
    assert 'error' in response.json


def test_logs_do_not_include_body(client, application, caplog):
    with caplog.at_level(logging.INFO, logger=application.logger.name):
        client.post('/api/requests', json=dict(VALID, description='SECRET_BODY_MARKER'))
    assert 'http_request' in caplog.text and '201' in caplog.text
    assert 'SECRET_BODY_MARKER' not in caplog.text


def test_concurrent_unique_ids(application):
    def submit(_index):
        with application.test_client() as client:
            response = client.post('/api/requests', json=VALID)
            assert response.status_code == 201
            return response.json['id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(submit, range(20)))
    assert len(set(ids)) == 20
    assert len(application.extensions['request_store'].all()) == 20


def test_memory_restart_loses_data():
    config = {'TESTING': True, 'APP_ENV': 'test', 'STORAGE_BACKEND': 'memory'}
    first = create_app(config)
    first.test_client().post('/api/requests', json=VALID)
    assert create_app(config).test_client().get('/api/requests').json == []


def test_sqlite_restart_preserves_data(tmp_path):
    config = {'TESTING': True, 'APP_ENV': 'test', 'STORAGE_BACKEND': 'database',
              'DATABASE_URL': 'sqlite:///' + (tmp_path / 'restart.db').as_posix()}
    first = create_app(config)
    item = first.test_client().post('/api/requests', json=VALID).json
    first.extensions['request_store'].engine.dispose()
    assert create_app(config).test_client().get(f"/api/requests/{item['id']}").json == item


@pytest.mark.parametrize('backend,url', [('memory', None), ('database', None),
                                         ('database', 'sqlite:///:memory:')])
def test_production_rejects_ephemeral_storage(backend, url):
    with pytest.raises(RuntimeError, match='external PostgreSQL'):
        create_app({'APP_ENV': 'production', 'STORAGE_BACKEND': backend, 'DATABASE_URL': url})


def test_database_unavailable_health(tmp_path, monkeypatch):
    application = create_app({'TESTING': True, 'APP_ENV': 'test',
                              'STORAGE_BACKEND': 'database',
                              'DATABASE_URL': 'sqlite:///' + (tmp_path / 'fail.db').as_posix()})
    def unavailable():
        raise OperationalError('query', {}, Exception('private database information'))
    monkeypatch.setattr(application.extensions['request_store'], 'ping', unavailable)
    response = application.test_client().get('/health')
    assert response.status_code == 503
    assert response.json == {'status': 'unhealthy'}
    assert b'private database' not in response.data
