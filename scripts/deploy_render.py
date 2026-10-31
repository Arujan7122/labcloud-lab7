"""Deploy exactly GITHUB_SHA; fail on missing configuration, failure or timeout."""
import json
import os
import re
import time
import urllib.error
import urllib.request


def main():
    required = ['RENDER_API_KEY', 'RENDER_SERVICE_ID', 'GITHUB_SHA']
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit('Configure production environment values: ' + ', '.join(missing))
    service_id = os.environ['RENDER_SERVICE_ID']
    commit = os.environ['GITHUB_SHA']
    if not re.fullmatch(r'srv-[a-z0-9]+', service_id) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise SystemExit('Invalid service ID or commit SHA')
    base = 'https://api.render.com/v1/services/' + service_id + '/deploys'
    token = os.environ['RENDER_API_KEY']

    def api(url, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers={
            'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise SystemExit(f'Render API returned HTTP {error.code}; inspect platform logs') from None

    deployed = api(base, {'commitId': commit, 'clearCache': 'do_not_clear'})
    deploy_id = deployed['id']
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        status = api(base + '/' + deploy_id)['status']
        print('Render deployment status:', status, flush=True)
        if status == 'live':
            return
        if status in {'build_failed', 'update_failed', 'pre_deploy_failed', 'canceled', 'deactivated'}:
            raise SystemExit('Deployment did not become live: ' + status)
        time.sleep(10)
    raise SystemExit('Deployment timed out after 15 minutes')


if __name__ == '__main__':
    main()
