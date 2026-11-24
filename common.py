import json
from datetime import datetime, timezone
from pathlib import Path
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

def secret(name):
    return Path('/run/secrets/'+name).read_text().strip()

def event(name, level='info', **fields):
    print(json.dumps(dict(ts=datetime.now(timezone.utc).isoformat(), level=level, event=name, **fields)), flush=True)

def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
