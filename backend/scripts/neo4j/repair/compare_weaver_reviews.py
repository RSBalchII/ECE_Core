#!/usr/bin/env python3
"""Compare two weaver CSV outputs (e.g., baseline vs chunked) and report metrics.

Usage:
  python compare_weaver_reviews.py baseline.csv chunked.csv

Reports:
  - count of rows
  - mean, median, top N scores
  - counts above threshold (e.g., 0.75), default threshold 0.75
  - average delta_diff
  - prints the Top 5 rows with (score, delta_diff, s_excerpt, orig_excerpt)
"""
import csv
import sys
from typing import List, Tuple
from statistics import mean, median
import argparse


def read_csv_rows(path: str) -> Tuple[List[str], List[List[str]]]:
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        r = csv.reader(fh)
        rows = list(r)
        if not rows:
            return [], []
        header = rows[0]
        data = rows[1:]
        return header, data


def index_of(header: List[str], names: List[str]):
    for n in names:
        if n in header:
            return header.index(n)
    return None


def parse_rows(header: List[str], data: List[List[str]]):
    score_idx = index_of(header, ['score', 'score' , 'score'])
    second_idx = index_of(header, ['second_score', 'second_score'])
    delta_idx = index_of(header, ['delta_diff', 'delta_diff'])
    s_excerpt_idx = index_of(header, ['s_excerpt'])
    orig_excerpt_idx = index_of(header, ['orig_excerpt'])

    parsed = []
    for r in data:
        try:
            score = float(r[score_idx]) if score_idx is not None and r[score_idx] else 0.0
        except Exception:
            score = 0.0
        try:
            second = float(r[second_idx]) if second_idx is not None and r[second_idx] else 0.0
        except Exception:
            second = 0.0
        try:
            delta = float(r[delta_idx]) if delta_idx is not None and r[delta_idx] else (score - second)
        except Exception:
            delta = (score - second)
        s_excerpt = r[s_excerpt_idx] if s_excerpt_idx is not None and s_excerpt_idx < len(r) else ''
        orig_excerpt = r[orig_excerpt_idx] if orig_excerpt_idx is not None and orig_excerpt_idx < len(r) else ''
        parsed.append({'score': score, 'second': second, 'delta': delta, 's_excerpt': s_excerpt, 'orig_excerpt': orig_excerpt, 'raw': r})
    return parsed


def summarize(name: str, rows: List[dict], threshold: float = 0.75):
    if not rows:
        print(f"-- {name}: no rows --")
        return
    scores = [r['score'] for r in rows]
    deltas = [r['delta'] for r in rows]
    top5 = sorted(rows, key=lambda x: x['score'], reverse=True)[:5]
    print(f"=== {name} ===")
    print(f"Count: {len(rows)}")
    print(f"Mean score: {mean(scores):.4f} ; Median score: {median(scores):.4f}")
    print(f"Mean delta_diff: {mean(deltas):.4f} ; Median delta_diff: {median(deltas):.4f}")
    print(f"Above threshold ({threshold}): {sum(1 for s in scores if s >= threshold)}")
    print("Top 5:")
    for i, r in enumerate(top5, 1):
        print(f"{i}. score={r['score']:.4f}, delta={r['delta']:.4f}")
        s = (r['s_excerpt'] or '').replace('\n', ' ')[:200]
        o = (r['orig_excerpt'] or '').replace('\n', ' ')[:200]
        print(f"   summary: {s}")
        print(f"   origin:  {o}")
    print('')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline', type=str, help='Baseline CSV path')
    parser.add_argument('chunked', type=str, help='Chunked CSV path')
    parser.add_argument('--threshold', type=float, default=0.75, help='Threshold for matches')
    args = parser.parse_args()

    header_b, rows_b = read_csv_rows(args.baseline)
    header_c, rows_c = read_csv_rows(args.chunked)
    parsed_b = parse_rows(header_b, rows_b)
    parsed_c = parse_rows(header_c, rows_c)

    summarize('Baseline', parsed_b, threshold=args.threshold)
    summarize('Chunked', parsed_c, threshold=args.threshold)

    # compare top 5 side-by-side
    top_n = 5
    print('--- Top-5 comparison (Baseline -> Chunked) ---')
    topb = sorted(parsed_b, key=lambda x: x['score'], reverse=True)[:top_n]
    topc = sorted(parsed_c, key=lambda x: x['score'], reverse=True)[:top_n]
    for i in range(top_n):
        s_b = topb[i] if i < len(topb) else None
        s_c = topc[i] if i < len(topc) else None
        print(f"Rank {i+1}:")
        if s_b:
            print(f"  Baseline: score={s_b['score']:.4f}, delta={s_b['delta']:.4f}")
        else:
            print("  Baseline: None")
        if s_c:
            print(f"  Chunked:  score={s_c['score']:.4f}, delta={s_c['delta']:.4f}")
        else:
            print("  Chunked: None")
        print('')


if __name__ == '__main__':
    main()
