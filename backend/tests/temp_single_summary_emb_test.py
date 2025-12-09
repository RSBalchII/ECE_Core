import httpx
from neo4j import GraphDatabase
from src.config import Settings
import csv
import math
import time
import random
import argparse

settings = Settings()

EMB_ENDPOINT = ("http://127.0.0.1:8081/v1/embeddings")
MODEL = "embeddinggemma-300m.Q8_0"

client = httpx.Client(timeout=30)

def get_embedding(text, retries=3, backoff=0.5):
    try:
        r = client.post(EMB_ENDPOINT, json={"model": MODEL, "input": text})
        r.raise_for_status()
        data = r.json()
        return data['data'][0]['embedding']
    except Exception as e:
        if retries > 0:
            time.sleep(backoff + (random.random() * backoff))
            return get_embedding(text, retries - 1, backoff * 2)
        print('embed error:', e)
        return None


def get_embeddings(texts, retries=2, backoff=0.5):
    try:
        r = client.post(EMB_ENDPOINT, json={"model": MODEL, "input": texts})
        r.raise_for_status()
        data = r.json()
        return [d['embedding'] for d in data['data']]
    except Exception as e:
        # Attempt fallback to chunked single-request mode
        print('embed batch error:', e, ' - falling back to per-item requests')
        results = []
        for t in texts:
            emb = get_embedding(t, retries=retries, backoff=backoff)
            results.append(emb)
        return results


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x*y for x,y in zip(a,b))
    sa = sum(x*x for x in a)
    sb = sum(y*y for y in b)
    if sa == 0 or sb == 0:
        return 0.0
    return dot / (math.sqrt(sa) * math.sqrt(sb))


def main(candidate_limit=200, batch_size=8, delay=0.2):
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    with driver.session() as session:
        # Pick a short summary to test
        res = session.run("MATCH (s:Memory) WHERE s.category='summary' AND size(s.content) < 500 AND NOT (s)-[:DISTILLED_FROM]->() RETURN elementId(s) as s_eid, s.app_id as s_app_id, s.content as content LIMIT 1").single()
        if not res:
            print('No short summary available.')
            return
        s_eid = res['s_eid']
        s_content = res['content'] or ''

        # Select candidate origins with small content size to avoid server errors
        cres = session.run(f"MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') AND size(orig.content) < 2000 RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.content as content, orig.created_at as orig_created_at LIMIT {candidate_limit}")
        candidates = list(cres)
        if not candidates:
            print('No candidates')
            return

    print('Selected summary:', s_eid, 'len=', len(s_content))
    print('Candidates:', len(candidates))

    s_emb = get_embedding(s_content[:2048])
    candidate_texts = [ (c['content'] or '')[:2048] for c in candidates]
    # batch into smaller chunks
    batch_size = 8
    c_embs = []
    for i in range(0, len(candidate_texts), batch_size):
        chunk = candidate_texts[i:i+batch_size]
        embs = get_embeddings(chunk)
        # avoid hammering the server
        time.sleep(delay)
        c_embs.extend(embs)

    # Compute cosines
    rows = []
    for i, emb in enumerate(c_embs):
        score = cosine(s_emb, emb)
        rows.append((score, candidates[i]['orig_eid'], candidates[i].get('orig_app_id') or '', (candidates[i]['content'] or '')[:200]))

    rows = sorted(rows, key=lambda r: r[0], reverse=True)
    top3 = rows[:3]

    print('\nTop 3 candidates:')
    for score, eid, app_id, snippet in top3:
        print(score, eid, app_id)
        print(snippet)
        print('---')

    # Save CSV
    csv_path = 'temp_single_summary_emb_test.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['s_eid', 'orig_eid', 'orig_app_id', 'score', 'snippet'])
        for score, eid, app_id, snippet in rows:
            w.writerow([s_eid, eid, app_id, f"{score:.4f}", snippet])
    print('CSV saved to', csv_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate-limit', type=int, default=50)
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--delay', type=float, default=0.25)
    args = parser.parse_args()
    main(candidate_limit=args.candidate_limit, batch_size=args.batch_size, delay=args.delay)
