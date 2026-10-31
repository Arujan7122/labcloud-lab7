"""LabCloud REST API. Run locally: python app.py."""
import json
import logging
import os
import threading
import time
from pathlib import Path

from flask import Flask, g, jsonify, request
from sqlalchemy import (Column, Integer, MetaData, String, Table, Text,
                        create_engine, insert, select, text)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

ALLOWED_CATEGORIES = {'computer', 'network', 'software'}
ALLOWED_PRIORITIES = {'low', 'medium', 'high'}


class MemoryStore:
    """Deliberately volatile store for task A; never use with multiple workers."""
    def __init__(self):
        self.items = {}
        self.next_id = 1
        self.lock = threading.RLock()

    def create(self, values):
        with self.lock:
            item = dict(values, id=self.next_id)
            self.items[self.next_id] = item
            self.next_id += 1
            return item.copy()

    def all(self):
        with self.lock:
            return [item.copy() for item in self.items.values()]

    def get(self, item_id):
        with self.lock:
            item = self.items.get(item_id)
            return item.copy() if item else None

    def ping(self):
        return True


class DatabaseStore:
    def __init__(self, url):
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql+psycopg://', 1)
        elif url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
        options = {'pool_pre_ping': True}
        if url.startswith('sqlite:'):
            options['connect_args'] = {'check_same_thread': False, 'timeout': 30}
            if url.endswith(':memory:'):
                options['poolclass'] = StaticPool
        self.engine = create_engine(url, **options)
        meta = MetaData()
        self.table = Table(
            'equipment_requests', meta,
            Column('id', Integer, primary_key=True),
            Column('title', String(120), nullable=False),
            Column('category', String(16), nullable=False),
            Column('priority', String(8), nullable=False),
            Column('description', Text, nullable=False),
        )
        # Serialize first-start schema creation across Gunicorn workers.
        with self.engine.begin() as connection:
            if self.engine.dialect.name == 'sqlite':
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            elif self.engine.dialect.name == 'postgresql':
                connection.execute(text('SELECT pg_advisory_xact_lock(7007007)'))
            meta.create_all(connection)

    def create(self, values):
        with self.engine.begin() as connection:
            item_id = connection.execute(insert(self.table).values(**values)).inserted_primary_key[0]
            return dict(values, id=item_id)

    def all(self):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(
                select(self.table).order_by(self.table.c.id)).mappings()]

    def get(self, item_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(self.table).where(
                self.table.c.id == item_id)).mappings().first()
            return dict(row) if row else None

    def ping(self):
        with self.engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return True


def create_app(config=None):
    application = Flask(__name__)
    application.json.ensure_ascii = False
    application.config.update(
        APP_ENV=os.getenv('APP_ENV', 'development'),
        APP_VERSION=os.getenv('APP_VERSION', '1.2.0'),
        STORAGE_BACKEND=os.getenv('STORAGE_BACKEND', 'database'),
        DATABASE_URL=os.getenv('DATABASE_URL'),
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if config:
        application.config.update(config)
    backend = application.config['STORAGE_BACKEND']
    database_url = application.config['DATABASE_URL']
    if backend not in {'memory', 'database'}:
        raise RuntimeError('STORAGE_BACKEND must be memory or database')
    if application.config['APP_ENV'] == 'production':
        if backend != 'database' or not database_url or not database_url.startswith(
            ('postgres://', 'postgresql://', 'postgresql+psycopg://')
        ):
            raise RuntimeError('Production requires an external PostgreSQL DATABASE_URL')
    if backend == 'memory':
        store = MemoryStore()
    else:
        if not database_url:
            folder = Path(__file__).resolve().parent / 'data'
            folder.mkdir(exist_ok=True)
            database_url = 'sqlite:///' + (folder / 'labcloud.db').as_posix()
        store = DatabaseStore(database_url)
    application.extensions['request_store'] = store
    application.logger.setLevel(logging.INFO)

    @application.before_request
    def begin_request():
        g.started = time.perf_counter()

    @application.after_request
    def log_request(response):
        # Never log request bodies, headers, query strings or database credentials.
        application.logger.info(json.dumps({
            'event': 'http_request', 'method': request.method, 'path': request.path,
            'status': response.status_code,
            'duration_ms': round((time.perf_counter() - g.started) * 1000, 3),
        }))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def reject(message, code=400):
        return jsonify({'error': message}), code

    @application.get('/')
    def index():
        return jsonify(application='LabCloud', status='running',
                       environment=application.config['APP_ENV'],
                       version=application.config['APP_VERSION'],
                       revision=os.getenv('RENDER_GIT_COMMIT', 'local'),
                       instance=os.getenv('RENDER_INSTANCE_ID', 'local')), 200

    @application.get('/health')
    def health():
        try:
            store.ping()
        except SQLAlchemyError:
            application.logger.error('event=database_unavailable')
            return jsonify(status='unhealthy'), 503
        return jsonify(status='healthy'), 200

    @application.get('/api/requests')
    def get_requests():
        return jsonify(store.all()), 200

    @application.post('/api/requests')
    def create_request():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return reject('JSON объекті қажет')
        title = data.get('title')
        category = data.get('category')
        priority = data.get('priority')
        description = data.get('description', '')
        if not isinstance(title, str) or not title.strip():
            return reject('title бос болмауы керек')
        # Type checks must precede set membership: lists/dicts are unhashable.
        if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
            return reject('category мәні жарамсыз')
        if not isinstance(priority, str) or priority not in ALLOWED_PRIORITIES:
            return reject('priority мәні жарамсыз')
        if not isinstance(description, str):
            return reject('description мәтін болуы керек')
        if len(title.strip()) > 120 or len(description) > 1000:
            return reject('Мәтін ұзындығы шектен асты')
        item = store.create(dict(title=title.strip(), category=category,
                                 priority=priority, description=description.strip()))
        response = jsonify(item)
        response.status_code = 201
        response.headers['Location'] = f"/api/requests/{item['id']}"
        return response

    @application.get('/api/requests/<int:request_id>')
    def get_request(request_id):
        item = store.get(request_id)
        return (jsonify(item), 200) if item is not None else reject('Өтінім табылмады', 404)

    @application.errorhandler(SQLAlchemyError)
    def database_error(_error):
        application.logger.error('event=database_operation_failed')
        return reject('Деректер қоры уақытша қолжетімсіз', 503)

    @application.errorhandler(404)
    def not_found(_error):
        return reject('Мекенжай табылмады', 404)

    @application.errorhandler(405)
    def method_not_allowed(_error):
        return reject('HTTP әдісіне рұқсат жоқ', 405)

    @application.errorhandler(413)
    def too_large(_error):
        return reject('Сұрау көлемі шектен асты', 413)

    return application


app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    app.run(host=os.getenv('HOST', '0.0.0.0'), port=port, debug=False)
