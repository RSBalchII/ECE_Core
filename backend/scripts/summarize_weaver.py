import csv
from collections import Counter

file='c:/Users/rsbiiw/Projects/ECE_Core/logs/weaver_dry_run.csv'
rows=0
status_counts=Counter()
min_s=1e9
max_s=-1e9
sum_s=0.0
min_second=1e9
max_second=-1e9
sum_second=0.0
min_delta=1e9
max_delta=-1e9
sum_delta=0.0
count_s=0
count_second=0
count_delta=0
skipped_counts=Counter()
low_conf_count=0
run_ids=set()

with open(file, encoding='utf-8') as f:
    reader=csv.DictReader(f)
    for r in reader:
        rows+=1
        s=r['status']
        status_counts[s]+=1
        run_ids.add(r['run_id'])
        try:
            score=float(r['score'])
            count_s+=1
            min_s=min(min_s,score)
            max_s=max(max_s,score)
            sum_s+=score
            if score<0.38:
                low_conf_count+=1
        except:
            pass
        try:
            s2=float(r['second_score'])
            count_second+=1
            min_second=min(min_second,s2)
            max_second=max(max_second,s2)
            sum_second+=s2
        except:
            pass
        try:
            d=float(r['delta_diff'])
            count_delta+=1
            min_delta=min(min_delta,d)
            max_delta=max(max_delta,d)
            sum_delta+=d
        except:
            pass
        if s and s.startswith('skipped'):
            skipped_counts[s]+=1

print('Total rows:', rows)
print('\nStatus distribution:')
for k,v in status_counts.most_common():
    print(f'  {k}: {v}')

if count_s:
    print('\nScore: min',min_s,'max',max_s,'mean',sum_s/count_s)
if count_second:
    print('Second score: min',min_second,'max',max_second,'mean',sum_second/count_second)
if count_delta:
    print('Delta: min',min_delta,'max',max_delta,'mean',sum_delta/count_delta)

print('\nLow-confidence (<0.38) count:', low_conf_count)
print('\nSkipped status counts:')
for k,v in skipped_counts.items():
    print('  ',k, v)

print('\nUnique run_id count:', len(run_ids))
print('Some run_ids:')
for rid in list(run_ids)[:5]:
    print('  ',rid)

# Print a few top and bottom rows by score

rows_data=[]
with open(file, encoding='utf-8') as f:
    reader=csv.DictReader(f)
    for r in reader:
        try:
            r['_score']=float(r['score'])
        except:
            r['_score']=None
        rows_data.append(r)

rows_sorted=[r for r in rows_data if r['_score'] is not None]
rows_sorted.sort(key=lambda r:r['_score'], reverse=True)
print('\nTop 5 by score:')
for r in rows_sorted[:5]:
    print(f" score={r['_score']}, s_eid={r['s_eid']}, orig_eid={r['orig_eid']}, status={r['status']}")

print('\nBottom 5 by score:')
for r in rows_sorted[-5:]:
    print(f" score={r['_score']}, s_eid={r['s_eid']}, orig_eid={r['orig_eid']}, status={r['status']}")

# Print some problematic rows: high delta and low score

high_delta=[r for r in rows_sorted if r.get('delta_diff')]
high_delta.sort(key=lambda r: float(r['delta_diff']) if r['delta_diff'] else 0, reverse=True)
print('\nTop 5 high delta rows:')
for r in high_delta[:5]:
    print(f"delta={r['delta_diff']}, score={r['_score']}, s_eid={r['s_eid']}, orig_eid={r['orig_eid']}, status={r['status']}")

# Sample skipped rows examples for auditing
print('\nSample skipped rows (first 5):')
skipped_rows=[]
with open(file, encoding='utf-8') as f:
    reader=csv.DictReader(f)
    for r in reader:
        if r['status'] and r['status'].startswith('skipped'):
            skipped_rows.append(r)
print(' Count skipped rows:', len(skipped_rows))
for r in skipped_rows[:5]:
    print(r['status'], r['s_eid'], r['orig_eid'], (r['s_excerpt'] or '')[:50])
