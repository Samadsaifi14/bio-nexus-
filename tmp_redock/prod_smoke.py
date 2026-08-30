import base64, json, time, os, urllib.request

BASE = os.environ.get("SMOKE_BASE", "https://samad14-bio-nexus-api.hf.space")

def b64u(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

token = f'{b64u({"alg": "HS256", "typ": "JWT"})}.{b64u({"sub": "c054ad01-292a-4988-a4ba-a0aa671fbe28"})}.x'

def api(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:300]}

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
