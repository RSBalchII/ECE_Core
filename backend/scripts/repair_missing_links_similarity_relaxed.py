from neo4j import GraphDatabase
from src.config import Settings
import json
import re
import argparse
import csv
import os

def normalize_text(text: str) -> set:
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t for t in cleaned.split() if t and len(t) > 2]
    return set(tokens)

def jaccard(a:set, b:set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return inter / union if union else 0.0

def run_repair(threshold: float = 0.06, limit: int = 2000, candidate_limit:int | None = None, dry_run: bool = False, csv_out: str = None):
    s = Settings()
    from src.config import settings as global_settings
    if candidate_limit is None:
        candidate_limit = getattr(global_settings, 'weaver_candidate_limit', 200)
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    with driver.session() as session:
        srows = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() RETURN elementId(s) as s_eid, s.app_id as s_app_id, s.content as content, s.metadata as metadata LIMIT $limit", {'limit': limit})
        created = 0
        for sr in srows:
            s_eid = sr['s_eid']
            s_content = sr['content'] or ''
            s_meta = {}
            try:
                s_meta = json.loads(sr['metadata']) if sr['metadata'] else {}
            except Exception:
                s_meta = {}
            s_norm = normalize_text(s_content)
            s_tok = s_meta.get('original_token_count') or s_meta.get('token_count')
            candidates = []
            if s_tok:
                try:
                    st = int(s_tok)
                    est_chars = st * 4
                    min_chars = int(max(200, est_chars * 0.5))
                    max_chars = int(est_chars * 1.6)
                    q = """
                        MATCH (orig:Memory)
                        WHERE (orig.category IS NULL OR orig.category <> 'summary')
                          AND size(orig.content) >= $min_chars
                          AND size(orig.content) <= $max_chars
                        RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.content as content
                        LIMIT $candidate_limit
                    """
                    cres = session.run(q, {'min_chars': min_chars, 'max_chars': max_chars, 'candidate_limit': candidate_limit})
                    for r2 in cres:
                        candidates.append({'eid': r2['orig_eid'], 'app_id': r2.get('orig_app_id'), 'content': r2['content'], 'norm': normalize_text(r2['content'])})
                except Exception:
                    candidates = []
            if not candidates:
                cres = session.run("MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.content as content LIMIT $candidate_limit", {'candidate_limit': candidate_limit})
                for r2 in cres:
                    candidates.append({'eid': r2['orig_eid'], 'app_id': r2.get('orig_app_id'), 'content': r2['content'], 'norm': normalize_text(r2['content'])})
            best = None
            best_score = 0.0
            for o in candidates:
                score = jaccard(s_norm, o['norm'])
                if score > best_score:
                    best_score = score
                    best = o
            if best and best_score >= threshold:
                if dry_run:
                    row = [str(s_eid), str(sr.get('s_app_id') if sr.get('s_app_id') else ''), str(s_content[:200] if s_content else ''), str(best['eid']), str(best.get('app_id') if best.get('app_id') else ''), str(best.get('content')[:200] if best.get('content') else ''), f"{best_score:.4f}", 'similarity_relaxed']
                    if csv_out:
                        write_header = not (os.path.exists(csv_out) and os.path.getsize(csv_out) > 0)
                        with open(csv_out, 'a', newline='', encoding='utf-8') as fh:
                            w = csv.writer(fh)
                            if write_header:
                                w.writerow(['s_eid', 's_app_id', 's_content_snippet', 'orig_eid', 'orig_app_id', 'orig_content_snippet', 'score', 'method'])
                            w.writerow(row)
                    else:
                        print(f"DRY RELAXED SIM: s={s_eid} -> orig={best['eid']} score={best_score:.4f}")
                else:
                    # Make the relationship; allow linking to orig regardless of other incoming relationships
                    if best.get('app_id'):
                        # prefer app_id-based linking
                        session.run("MATCH (s:Memory {app_id: $s_app}), (orig:Memory {app_id: $orig_app}) MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_app': str(sr.get('s_app_id')), 'orig_app': str(best.get('app_id'))})
                    else:
                        session.run("MATCH (s),(orig) WHERE elementId(s) = $s_eid AND elementId(orig) = $orig_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_eid': str(best['eid'])})
                created += 1
        print(f"Created {created} relationships via relaxed similarity heuristic (threshold {threshold})")
    driver.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Relaxed similarity repair for missing DISTILLED_FROM links')
    parser.add_argument('--threshold', '-t', default=0.06, type=float, help='Similarity threshold (Jaccard)')
    parser.add_argument('--limit', '-l', default=2000, type=int, help='Limit number of summary candidates')
    parser.add_argument('--candidate-limit', '-c', default=None, type=int, help='Limit candidate origins per summary (use .env default when not set)')
    parser.add_argument('--dry-run', action='store_true', help='Do not write DB changes; instead emit candidate pairs or write CSV')
    parser.add_argument('--csv-out', type=str, default=None, help='If set, append dry-run candidate pairs to this CSV file')
    args = parser.parse_args()
    run_repair(threshold=args.threshold, limit=args.limit, candidate_limit=args.candidate_limit, dry_run=args.dry_run, csv_out=args.csv_out)
