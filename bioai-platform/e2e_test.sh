#!/usr/bin/env bash
set -e

BACKEND="http://localhost:8000"

SEQUENCE=">query_ubiquitin
MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"

echo "=== 1. Submit pipeline job ==="
RESPONSE=$(curl -s -X POST "$BACKEND/api/pipelines/run" \
  -H "Content-Type: application/json" \
  -d "{\"sequence\": \"$SEQUENCE\", \"pipeline_type\": \"protein_analysis\"}")

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
  echo "ERROR: No job_id in response. Check backend logs."
  exit 1
fi

echo ""
echo "=== 2. Job ID: $JOB_ID ==="
echo "Polling status every 3s (EBI BLAST takes 15-60s)..."
echo ""

for i in $(seq 1 40); do
  sleep 3
  STATUS_RESP=$(curl -s "$BACKEND/api/jobs/$JOB_ID")
  STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null)
  STEPS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('steps_completed', []))" 2>/dev/null)
  
  echo "  [${i}] status=$STATUS  steps=$STEPS"
  
  if [ "$STATUS" = "complete" ]; then
    echo ""
    echo "=== 3. Complete! Checking context_json ==="
    RESULT=$(curl -s "$BACKEND/api/jobs/$JOB_ID")
    echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ctx = d.get('context_json', d)
print('context_json keys:', list(ctx.keys()) if isinstance(ctx, dict) else type(ctx))
blast = ctx.get('blast', {})
hits = blast.get('hits', [])
print(f'BLAST hits: {len(hits)}')
if hits:
    print(f'  top hit: {hits[0].get(\"accession\",\"?\")} e={hits[0].get(\"evalue\",\"?\")}')
uniprot = ctx.get('uniprot', {})
print(f'UniProt function: {str(uniprot.get(\"function\",\"?\"))[:80]}')
alphafold = ctx.get('alphafold', {})
print(f'AlphaFold pLDDT: {alphafold.get(\"confidence\",\"?\")}')
print(f'AlphaFold PDB URL: {alphafold.get(\"pdb_url\",\"?\")}')
" 2>/dev/null || echo "$RESULT" | head -c 500
    
    echo ""
    echo "=== 4. Testing AI stream (first 200 chars) ==="
    curl -s -N --max-time 15 "$BACKEND/api/results/$JOB_ID/stream" | head -c 200
    echo ""
    echo ""
    echo "SUCCESS: full pipeline works end-to-end."
    exit 0
  fi
  
  if [ "$STATUS" = "failed" ]; then
    echo ""
    echo "FAILED. Full job record:"
    curl -s "$BACKEND/api/jobs/$JOB_ID" | python3 -m json.tool 2>/dev/null
    exit 1
  fi
done

echo "TIMEOUT: job still '$STATUS' after 120s. Check backend logs."
