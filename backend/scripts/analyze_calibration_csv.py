#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict, Counter

CSV='calibration_run.csv'
if len(sys.argv) > 1:
    CSV = sys.argv[1]

scores = []
count_by_bucket = defaultdict(int)
pairs = []
unique_summaries = set()

with open(CSV, 'r', encoding='utf-8') as fh:
    rdr = csv.DictReader(fh)
    for r in rdr:
        try:
            s_eid = r.get('s_eid')
            if not s_eid:
                continue
            score = float(r.get('score') or 0.0)
            scores.append(score)
            unique_summaries.add(s_eid)
            pairs.append((score, r))
            # bucketning into 0.05 increments
            bucket = int(score*20)/20.0
            count_by_bucket[bucket]+=1
        except Exception:
            continue

scores.sort()

print('CSV:', CSV)
print('Total candidate rows:', len(scores))
print('Unique summaries:', len(unique_summaries))
print('Score distribution (bucket -> count, bucket size=0.05):')
for b in sorted(count_by_bucket.keys()):
    print(f'  {b:.2f} -> {count_by_bucket[b]}')

# compute threshold counts
for thr in [0.5, 0.6, 0.65, 0.7, 0.75]:
    c = sum(1 for s in scores if s >= thr)
    print(f'Count >= {thr:.2f}: {c}')

# top results
pairs_sorted = sorted(pairs, key=lambda x: x[0], reverse=True)
print('\nTop 10 scored pairs:')
for s,r in pairs_sorted[:10]:
    print(f' {s:.4f} s={r.get("s_eid")} orig={r.get("orig_eid")}')

# pick 5 pairs in 0.60-0.70 range
cand_60_70 = [r for s,r in pairs if s >= 0.6 and s < 0.7]
print('\nNumber of pairs between 0.60 and 0.70:', len(cand_60_70))
for r in cand_60_70[:5]:
    print('---')
    print('Score:', r.get('score'))
    print('s_eid:', r.get('s_eid'))
    print('orig_eid:', r.get('orig_eid'))
    print('s_excerpt:', (r.get('s_excerpt') or '')[:200])
    print('orig_excerpt:', (r.get('orig_excerpt') or '')[:200])

print('\nDone')
