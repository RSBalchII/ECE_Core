from neo4j import GraphDatabase
from src.config import Settings
import json
import re
import argparse
import csv
import os
from collections import Counter

def normalize_text(text: str) -> set:
    if not text:
        return set()
    # Lowercase, remove non-word characters, split
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t for t in cleaned.split() if t and len(t) > 2]
    return set(tokens)

def jaccard(a:set, b:set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return inter / union if union else 0.0

def run_repair(threshold: float = 0.18, limit: int = 2000, candidate_limit: int | None = None, dry_run: bool = False, csv_out: str = None):
    s = Settings()
    from src.config import settings as global_settings
    if candidate_limit is None:
        candidate_limit = getattr(global_settings, 'weaver_candidate_limit', 200)
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    with driver.session() as session:
        # Get missing summaries
        srows = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() RETURN elementId(s) as s_eid, s.app_id as s_app_id, s.created_at as s_created_at, s.content as content, s.metadata as metadata LIMIT $limit", {'limit': limit})
        created = 0
        for sr in srows:
            s_eid = sr['s_eid']
            s_app_id = sr.get('s_app_id')
            s_content = sr['content'] or ''
            s_meta = {}
            try:
                s_meta = json.loads(sr['metadata']) if sr['metadata'] else {}
            except Exception:
                s_meta = {}
            s_norm = normalize_text(s_content)
            s_tok = s_meta.get('original_token_count') or s_meta.get('token_count')
            # Query Neo4j for candidates using character-length heuristic
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
                          AND NOT (() -[:DISTILLED_FROM]->(orig))
                          AND size(orig.content) >= $min_chars
                          AND size(orig.content) <= $max_chars
                        RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content
                        LIMIT $candidate_limit
                    """
                    cres = session.run(q, {'min_chars': min_chars, 'max_chars': max_chars, 'candidate_limit': candidate_limit})
                    for r2 in cres:
                        candidates.append({'eid': r2['orig_eid'], 'app_id': r2.get('orig_app_id'), 'created_at': r2.get('o_created_at'), 'content': r2['content'], 'norm': normalize_text(r2['content'])})
                except Exception:
                    candidates = []
            # Fallback: if we didn't find candidates by token heuristic, broaden search
            if not candidates:
                cres = session.run("MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') AND NOT (() -[:DISTILLED_FROM]->(orig)) RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content LIMIT $candidate_limit", {'candidate_limit': candidate_limit})
                for r2 in cres:
                    candidates.append({'eid': r2['orig_eid'], 'app_id': r2.get('orig_app_id'), 'created_at': r2.get('o_created_at'), 'content': r2['content'], 'norm': normalize_text(r2['content'])})
            # Score candidates by jaccard
            best = None
            best_score = 0.0
            for o in candidates:
                score = jaccard(s_norm, o['norm'])
                if score > best_score:
                    best_score = score
                    best = o
            if best and best_score >= threshold:
                # Prefer linking by app_id if present, otherwise fallback to elementId
                if dry_run:
                    # write CSV or print
                    row = [str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), str(best['eid']), str(best.get('app_id') if best.get('app_id') else ''), str(best.get('created_at') if best.get('created_at') else ''), f"{best_score:.4f}", 'similarity']
                    if csv_out:
                        write_header = not (os.path.exists(csv_out) and os.path.getsize(csv_out) > 0)
                        with open(csv_out, 'a', newline='', encoding='utf-8') as fh:
                            w = csv.writer(fh)
                            if write_header:
                                w.writerow(['s_eid', 's_app_id', 's_created_at', 'orig_eid', 'orig_app_id', 'orig_created_at', 'score', 'method'])
                            w.writerow(row)
                    else:
                        print(f"DRY SIM: s={s_eid} -> orig={best['eid']} score={best_score:.4f}")
                else:
                    if best.get('app_id') and s_app_id:
                        session.run("MATCH (s:Memory{app_id: $s_app_id}), (orig:Memory{app_id: $orig_app_id}) MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_app_id': s_app_id, 'orig_app_id': best.get('app_id')})
                    else:
                        session.run("MATCH (s),(orig) WHERE elementId(s) = $s_eid AND elementId(orig) = $orig_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_eid': str(best['eid'])})
                created += 1
        print(f"Created {created} relationships via similarity heuristic (threshold {threshold})")
    driver.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Repair similarity-based missing DISTILLED_FROM links')
    parser.add_argument('--threshold', '-t', default=0.18, type=float, help='Similarity threshold (Jaccard)')
    parser.add_argument('--limit', '-l', default=2000, type=int, help='Limit number of summary candidates')
    parser.add_argument('--candidate-limit', '-c', default=None, type=int, help='Limit candidate origins per summary (use .env default if not provided)')
    parser.add_argument('--dry-run', action='store_true', help='Do not write DB changes; instead emit candidate pairs or write CSV')
    parser.add_argument('--csv-out', type=str, default=None, help='If set, append dry-run candidate pairs to this CSV file')
    args = parser.parse_args()
    run_repair(threshold=args.threshold, limit=args.limit, candidate_limit=args.candidate_limit, dry_run=args.dry_run, csv_out=args.csv_out)
