"""Exercise the real HTTP API and record a small bounded load test."""
import argparse
import json
import math
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def call(base, path, method='GET', body=None, raw=None):
    payload = raw if raw is not None else (
        json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None)
    req = urllib.request.Request(base + path, data=payload, method=method,
                                 headers={'Content-Type': 'application/json'})
    started = time.perf_counter()
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        data = response.read().decode('utf-8')
        return {'status': response.status, 'body': json.loads(data),
                'elapsed_ms': round((time.perf_counter() - started) * 1000, 3)}


def verify(base, count=75, public=False):
    valid = {'title': 'Желілік коммутаторды тексеру', 'category': 'network',
             'priority': 'high', 'description': 'Зертханалық желідегі байланысты тексеру'}
    checks = []

    def check(name, path, expected, method='GET', body=None, raw=None):
        result = call(base, path, method, body, raw)
        checks.append(dict(name=name, expected_status=expected, **result,
                           passed=result['status'] == expected))
        return result

    index = check('index', '/', 200)
    health = check('health', '/health', 200)
    checks[-1]['passed'] &= health['body'] == {'status': 'healthy'}
    created = check('valid_post', '/api/requests', 201, 'POST', valid)
    item_id = created['body'].get('id', 0)
    reread = check('read_by_id', f'/api/requests/{item_id}', 200)
    checks[-1]['passed'] &= reread['body'] == created['body']
    check('empty_title', '/api/requests', 400, 'POST', dict(valid, title='   '))
    check('invalid_category', '/api/requests', 400, 'POST', dict(valid, category='unknown'))
    check('invalid_priority', '/api/requests', 400, 'POST', dict(valid, priority='urgent'))
    check('wrong_type', '/api/requests', 400, 'POST', dict(valid, category=[]))
    check('too_long', '/api/requests', 400, 'POST', dict(valid, title='x' * 121))
    check('missing_field', '/api/requests', 400, 'POST', {'title': 'Тексеру', 'category': 'network'})
    check('malformed_json', '/api/requests', 400, 'POST', raw=b'{broken')
    check('missing_id', '/api/requests/2147483647', 404)
    listed = check('list_requests', '/api/requests', 200)
    checks[-1]['passed'] &= created['body'] in listed['body']
    samples = []
    for _ in range(count):
        try:
            result = call(base, '/health')
            samples.append({'status': result['status'], 'elapsed_ms': result['elapsed_ms']})
        except (OSError, ValueError):
            samples.append({'status': 0, 'elapsed_ms': 30000})
        time.sleep(0.05)  # Sequential traffic only; at most ~20 requests/second.
    values = sorted(item['elapsed_ms'] for item in samples)
    success = sum(item['status'] == 200 for item in samples)
    return {
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'public' if public else 'local', 'base_url': base,
        'version': index['body'].get('version'), 'created_id': item_id,
        'checks': checks, 'all_passed': all(item['passed'] for item in checks) and success == count,
        'load': {'requests': count, 'successful': success, 'success_percent': success / count * 100,
                 'mean_ms': round(statistics.mean(values), 3),
                 'p95_ms': values[math.ceil(0.95 * count) - 1],
                 'min_ms': values[0], 'max_ms': values[-1], 'samples': samples},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default=os.getenv('PUBLIC_URL'))
    parser.add_argument('--count', type=int, default=75)
    parser.add_argument('--output', default='evidence/http.json')
    parser.add_argument('--public', action='store_true')
    args = parser.parse_args()
    if not args.url:
        parser.error('--url or PUBLIC_URL is required')
    if not 50 <= args.count <= 100:
        parser.error('--count must be between 50 and 100')
    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username:
        parser.error('Expected an HTTP(S) base URL without credentials')
    if args.public and (parsed.scheme != 'https' or parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
        parser.error('--public requires a real HTTPS service URL')
    result = verify(args.url.rstrip('/'), args.count, args.public)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in {'checks', 'load'}},
                     ensure_ascii=False))
    print(json.dumps({key: value for key, value in result['load'].items() if key != 'samples'}))
    raise SystemExit(0 if result['all_passed'] else 1)


if __name__ == '__main__':
    main()
