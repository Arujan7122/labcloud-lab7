"""Real process restarts, HTTP tests, failure isolation and release replacement."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from verify_http import call, verify

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'
EVIDENCE.mkdir(exist_ok=True)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def start(backend, name, version='1.1.0', url=None):
    port = free_port()
    env = dict(os.environ, APP_ENV='test', STORAGE_BACKEND=backend,
               PORT=str(port), HOST='127.0.0.1', APP_VERSION=version, PYTHONIOENCODING='utf-8')
    env.pop('DATABASE_URL', None)
    if url:
        env['DATABASE_URL'] = url
    log = (EVIDENCE / f'{name}.log').open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT,
                               env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f'http://127.0.0.1:{port}'
    for _ in range(100):
        if process.poll() is not None:
            log.close()
            raise RuntimeError('Server startup failed; inspect ' + name)
        try:
            if call(base, '/health')['status'] == 200:
                return process, log, base
        except OSError:
            pass
        time.sleep(0.1)
    process.terminate()
    process.wait(timeout=10)
    log.close()
    raise RuntimeError('Startup timeout')


def stop(process, log):
    process.terminate()
    process.wait(timeout=10)
    log.close()


def main():
    summary = {'scope': 'local processes; not cloud or Docker', 'persistence': {}}
    valid = {'title': 'Қайта іске қосу сынағы', 'category': 'software', 'priority': 'low'}
    for backend in ['memory', 'database']:
        db = EVIDENCE / 'restart.sqlite3'
        # New unique file on every run; preserve previous evidence databases.
        db = db.with_name(f'restart-{time.time_ns()}.sqlite3')
        url = 'sqlite:///' + db.as_posix()
        process, log, base = start(backend, backend + '-before', url=url)
        try:
            created = call(base, '/api/requests', 'POST', valid)['body']
            before = call(base, '/api/requests')['body']
        finally:
            stop(process, log)
        process, log, base = start(backend, backend + '-after', url=url)
        try:
            after = call(base, '/api/requests')['body']
            summary['persistence'][backend] = {
                'before': before, 'after': after, 'preserved': created in after,
                'new_process_pid': process.pid,
            }
        finally:
            stop(process, log)
    assert not summary['persistence']['memory']['preserved']
    assert summary['persistence']['database']['preserved']

    # Isolated invalid startup target: no modification to a production resource.
    bad = subprocess.run([sys.executable, '-c', 'from labcloud_typo import app'],
                         cwd=ROOT, capture_output=True, text=True)
    (EVIDENCE / 'D-startup-broken.log').write_text(bad.stderr, encoding='utf-8')
    assert bad.returncode != 0 and 'ModuleNotFoundError' in bad.stderr
    summary['diagnostics'] = {'broken_exit_code': bad.returncode,
                              'cause': 'ModuleNotFoundError: labcloud_typo',
                              'fixed_target': 'app:app'}

    # An intentionally failing health assertion, outside the actual passing test suite.
    code = "from app import app\ndef test_wrong_health():\n    assert app.test_client().get('/health').status_code == 503\n"
    fault = EVIDENCE / 'intentional_failure.py'
    fault.write_text(code, encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'pytest', str(fault), '-v'],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    (EVIDENCE / 'B-intentional-test-failure.log').write_text(
        result.stdout + result.stderr, encoding='utf-8')
    assert result.returncode == 1 and 'FAILED' in result.stdout
    summary['intentional_test_failure_exit_code'] = result.returncode

    db_url = 'sqlite:///' + (EVIDENCE / f'release-{time.time_ns()}.sqlite3').as_posix()
    process, log, base = start('database', 'http-release-1', '1.0.0', db_url)
    try:
        full = verify(base, 75)
        assert full['all_passed']
        (EVIDENCE / 'local-http.json').write_text(
            json.dumps(full, ensure_ascii=False, indent=2), encoding='utf-8')
        old_item = call(base, f"/api/requests/{full['created_id']}")['body']
    finally:
        stop(process, log)
    process, log, base = start('database', 'http-release-2-fixed', '1.1.0', db_url)
    try:
        replacement = verify(base, 50)
        assert replacement['all_passed']
        assert call(base, f"/api/requests/{full['created_id']}")['body'] == old_item
        summary['release'] = {'before': full['version'], 'after': replacement['version'],
                              'health_after': call(base, '/health'),
                              'request_preserved': True, 'scope': 'local process replacement'}
        summary['diagnostics']['fixed_health'] = call(base, '/health')['status']
        (EVIDENCE / 'local-release-2.json').write_text(
            json.dumps(replacement, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        stop(process, log)
    (EVIDENCE / 'experiments.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
