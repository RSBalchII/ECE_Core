#!/usr/bin/env python3
import csv
from collections import Counter

COUNTER=Counter()
rows=0
with open('full_clean_report.csv','r',encoding='utf-8') as f:
    rdr=csv.DictReader(f)
    for r in rdr:
        rows+=1
        COUNTER[r.get('status')]+=1

print('Processed rows:', rows)
print('Status counts:')
for k,v in COUNTER.items():
    print(' ',k, v)
