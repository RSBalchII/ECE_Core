#!/usr/bin/env python3
"""
Audit Memory node content quality and flag suspicious patterns.
Generates CSV with per-node flags and a top-line summary.

Usage:
  python scripts/audit_content_quality.py --limit 1000 --output audit_content.csv

"""
import argparse
import sys
import os

# Ensure repository root is on sys.path for imports like src.config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import csv
import json
import re
from neo4j import GraphDatabase
from src.config import Settings
from src.content_utils import is_json_like, is_html_like

# Emoji regex ranges (basic)
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]",
    flags=re.UNICODE,
)

SPAM_KEYWORDS = ['erotik', 'click here', 'buy now', 'free', 'cheap', 'subscribe now', 'http://', 'https://']
def emoji_ratio(text: str) -> float:
    if not text:
        return 0.0
    emoji_matches = EMOJI_PATTERN.findall(text)
    return len(emoji_matches) / max(1, len(text))


def has_spam_keywords(text: str):
    t = text.lower()
    return ','.join([k for k in SPAM_KEYWORDS if k in t])


def sanitize_snippet(s: str, max_len: int = 200):
    return (s or '').replace('\n', ' ').replace('\r', ' ').strip()[:max_len]


def non_ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return non_ascii / max(1, len(text))


def scan_nodes(limit: int = 1000, output: str = 'temp_content_audit.csv'):
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return

    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    with driver.session() as session:
        # Select memory nodes with optional limit. If limit <= 0, do a full scan.
        if limit and limit > 0:
            q = "MATCH (m:Memory) RETURN elementId(m) as eid, m.app_id as app_id, m.created_at as created_at, m.content as content LIMIT $limit"
            it = session.run(q, {'limit': limit})
        else:
            q = "MATCH (m:Memory) RETURN elementId(m) as eid, m.app_id as app_id, m.created_at as created_at, m.content as content"
            it = session.run(q)
        rows = [r for r in it]

    # CSV header
    header = ['eid', 'app_id', 'created_at', 'len', 'json_like', 'html_like', 'non_ascii_ratio', 'emoji_ratio', 'spam_keywords', 'technical_signal', 'suspect', 'snippet']
    suspicious = 0
    counters = {'json_like': 0, 'html_like': 0, 'non_ascii_high': 0, 'emoji_high': 0, 'spam_keywords': 0}
    total = len(rows)

    with open(output, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            eid = r['eid']
            app_id = r.get('app_id') if r.get('app_id') else ''
            created_at = r.get('created_at')
            content = r.get('content') or ''
            length = len(content)
            j_like = is_json_like(content)
            html_like = is_html_like(content)
            tech_signal = False
            try:
                from src.content_utils import has_technical_signal
                tech_signal = has_technical_signal(content)
            except Exception:
                tech_signal = False
            non_ascii = round(non_ascii_ratio(content), 4)
            emoji_r = round(emoji_ratio(content), 4)
            spam_k = has_spam_keywords(content)

            # Mark suspect if JSON/HTML-like or high non-ascii or spam keywords
            suspect = False
            if (j_like or html_like) and not tech_signal or non_ascii > 0.3 or emoji_r > 0.05 or spam_k:
                suspect = True
                suspicious += 1
                if j_like:
                    counters['json_like'] += 1
                if html_like:
                    counters['html_like'] += 1
                if non_ascii > 0.3:
                    counters['non_ascii_high'] += 1
                if emoji_r > 0.05:
                    counters['emoji_high'] += 1
                if spam_k:
                    counters['spam_keywords'] += 1

            snippet = sanitize_snippet(content)
            w.writerow([eid, app_id, created_at, length, str(j_like), str(html_like), non_ascii, emoji_r, spam_k, str(tech_signal), str(suspect), snippet])

    print(f"Scanned {total} Memory nodes; suspect={suspicious} ({(suspicious/total*100) if total>0 else 0:.1f}%); report: {output}")
    print("Breakdown:")
    for k, v in counters.items():
        print(f"  {k}: {v}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--output', type=str, default='temp_content_audit.csv')
    args = parser.parse_args()
    scan_nodes(limit=args.limit, output=args.output)
