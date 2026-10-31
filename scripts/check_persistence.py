"""Snapshot a public request, then compare it after restart or deployment."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from verify_http import call


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--snapshot', default='evidence/persistence-snapshot.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    base = args.url.rstrip('/')
    path = Path(args.snapshot)
    release = call(base, '/')
    if release['status'] != 200:
        raise SystemExit('Application unavailable')
    if args.check:
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        if snapshot['url'] != base:
            raise SystemExit('Snapshot belongs to a different URL')
        response = call(base, '/api/requests/' + str(snapshot['request']['id']))
        result = {'checked_at': datetime.now(timezone.utc).isoformat(),
                  'before': snapshot, 'release_after': release['body'],
                  'request_after': response['body'],
                  'preserved': response['status'] == 200 and response['body'] == snapshot['request']}
        path.with_name(path.stem + '-after.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result['preserved'] else 1)
    if path.exists():
        raise SystemExit('Snapshot already exists; choose another path or use --check')
    response = call(base, '/api/requests', 'POST', {
        'title': 'Cloud persistence check', 'category': 'software', 'priority': 'low'})
    if response['status'] != 201:
        raise SystemExit('Request creation failed')
    snapshot = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'url': base,
                'release': release['body'], 'request': response['body']}
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Created snapshot for request', response['body']['id'])


if __name__ == '__main__':
    main()
