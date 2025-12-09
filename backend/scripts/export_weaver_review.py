import csv
from operator import itemgetter

in_file='c:/Users/rsbiiw/Projects/ECE_Core/logs/weaver_dry_run.csv'
out_file='c:/Users/rsbiiw/Projects/ECE_Core/logs/weaver_review.csv'

rows=[]
with open(in_file, encoding='utf-8') as f:
    reader=csv.DictReader(f)
    for r in reader:
        try:
            r['_score']=float(r['score'])
        except:
            r['_score']=None
        rows.append(r)

# Sort by score descending, take top 25
rows_with_score=[r for r in rows if r['_score'] is not None]
rows_with_score.sort(key=itemgetter('_score'), reverse=True)
selected=rows_with_score[:25]

# Columns to include
cols=['run_id','s_eid','s_app_id','s_created_at','orig_eid','orig_app_id','orig_created_at','score','second_score','delta_diff','num_candidates','method','status','s_excerpt','orig_excerpt','commit_ts']

with open(out_file,'w', encoding='utf-8', newline='') as f:
    writer=csv.DictWriter(f, fieldnames=cols)
    writer.writeheader()
    for r in selected:
        out={c: r.get(c,'') for c in cols}
        writer.writerow(out)

print('Exported', len(selected), 'rows to', out_file)
