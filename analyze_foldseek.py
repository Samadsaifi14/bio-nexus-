import sys, json
d = json.loads(sys.stdin.read())
r = d.get('raw', {})
results = r.get('results', [])
print(f"Number of results: {len(results)}")
for i in range(min(3, len(results))):
    alns = results[i].get('alignments', [])
    print(f"\nResult {i}:")
    print(f"  keys: {list(results[i].keys())[:5]}")
    print(f"  num alignments: {len(alns)}")
    if alns:
        a0 = alns[0]
        print(f"  first aln type: {type(a0).__name__}")
        if isinstance(a0, dict):
            print(f"  first aln keys: {list(a0.keys())[:15]}")
            print(f"  target: {a0.get('target','?')}")
            print(f"  score: {a0.get('score','?')}")
        elif isinstance(a0, list):
            print(f"  first aln len: {len(a0)}")
    for j, a in enumerate(alns):
        if type(a).__name__ != 'dict':
            print(f"  WARNING: alignment {j} is {type(a).__name__}, content: {str(a)[:200]}")
