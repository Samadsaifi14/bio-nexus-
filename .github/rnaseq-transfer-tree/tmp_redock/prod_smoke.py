import base64, json, time, os
from urllib.parse import urlparse

import httpx

DEFAULT_BASE = "https://samad14-bio-nexus-api.hf.space"
ALLOWED_HOSTS = {"samad14-bio-nexus-api.hf.space", "localhost", "127.0.0.1"}


def validated_base(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("SMOKE_BASE must use http or https")
    if not parsed.hostname or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"SMOKE_BASE host is not allowed: {parsed.hostname!r}")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("SMOKE_BASE must be a simple origin URL")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Non-local smoke endpoints must use HTTPS")
    return raw.rstrip("/")


BASE = validated_base(os.environ.get("SMOKE_BASE", DEFAULT_BASE))


def b64u(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


token = f'{b64u({"alg": "HS256", "typ": "JWT"})}.{b64u({"sub": "c054ad01-292a-4988-a4ba-a0aa671fbe28"})}.x'


def api(method, path, body=None):
    if not path.startswith("/api/"):
        raise ValueError("smoke-test path must stay under /api/")
    try:
        response = httpx.request(
            method,
            f"{BASE}{path}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
            follow_redirects=False,
        )
        if response.status_code >= 400:
            return {"http_error": response.status_code, "body": response.text[:300]}
        return response.json()
    except httpx.HTTPError as exc:
        return {"network_error": str(exc)[:300]}


job = api("POST", "/api/docking/run",
          {"pdb_id": "1STP", "smiles": "biotin", "exhaustiveness": 32})
print("create:", job)
if "job_id" not in job:
    raise SystemExit(1)

for i in range(40):
    time.sleep(15)
    s = api("GET", f"/api/docking/status/{job['job_id']}")
    st = s.get("status")
    print(f"[{i*15}s] {st}", s.get("error") or "")
    if st in ("complete", "failed", "error"):
        break

r = s.get("result") or {}
print("----")
print("status:", s.get("status"))
poses = r.get("poses") or []
print("best affinity:", poses[0].get("affinity") if poses else None)
print("grid_source:", r.get("grid_source"), "| vina_seed:", r.get("vina_seed"),
      "| exhaustiveness:", r.get("vina_exhaustiveness"))
bc = r.get("box_center")
print("box_center:", bc)
print("num_poses:", len(poses))
