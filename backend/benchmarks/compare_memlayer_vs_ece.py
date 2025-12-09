"""ECE_Core benchmark harness (ECE-only)

Usage:
    python compare_memlayer_vs_ece.py --ece-url http://localhost:8000

This script:
- Loads a small set of test facts and queries
- Indexes them into ECE_Core
- Runs queries, measures recall, rank, and latency
- Outputs a CSV and JSON summary under `benchmarks/results/`.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from typing import Dict, List, Any

import requests

BENCHMARK_DIR = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def load_testcases() -> List[Dict[str, Any]]:
    # Simple testcases: facts + queries
    return [
        {
            "id": "t1",
            "fact": "Alice works at TechCorp as a senior engineer.",
            "tags": ["employment", "alice"],
            "category": "fact",
            "query": "Where does Alice work?",
            "expected": "TechCorp",
        },
        {
            "id": "t2",
            "fact": "I prefer Dark mode and a 14-inch laptop.",
            "tags": ["preferences", "ui"],
            "category": "note",
            "query": "What UI mode do I prefer?",
            "expected": "Dark mode",
        },
        {
            "id": "t3",
            "fact": "Project Phoenix uses Python and React.",
            "tags": ["project", "tech"],
            "category": "project",
            "query": "What stack does Project Phoenix use?",
            "expected": "Python and React",
        },
    ]


def add_ece_memory(ece_url: str, session: requests.Session, fact: str, category: str, tags: List[str]):
    url = f"{ece_url.rstrip('/')}/memories"
    payload = {
        "category": category,
        "content": fact,
        "tags": tags,
    }
    resp = session.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def search_ece_memories(ece_url: str, session: requests.Session, tags: List[str], limit: int = 10):
    url = f"{ece_url.rstrip('/')}/memories/search"
    params = {"tags": ",".join(tags), "limit": limit}
    resp = session.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def run_ece_tests(ece_url: str, testcases: List[Dict[str, Any]]):
    session = requests.Session()
    results = []
    # Add facts
    for case in testcases:
        add_ece_memory(ece_url, session, case["fact"], case["category"], case["tags"])

    # Query
    for case in testcases:
        tags = case["tags"]
        start = time.perf_counter()
        r = search_ece_memories(ece_url, session, tags, limit=10)
        latency = time.perf_counter() - start
        found = False
        rank = None
        memories = r.get("memories", [])
        for i, mem in enumerate(memories):
            content = mem.get("content", "").lower()
            if case["expected"].lower() in content:
                found = True
                rank = i + 1
                break
        results.append({
            "id": case["id"],
            "system": "ECE_Core",
            "query": case["query"],
            "expected": case["expected"],
            "found": found,
            "rank": rank if rank else -1,
            "latency_ms": latency * 1000,
            "raw_memories": memories,
        })
    return results


# Memlayer integration removed — benchmark now focuses solely on ECE_Core


def run_ece_salience_test(ece_url: str, session: requests.Session):
    # Send a simulated chat that contains filler and salient facts
    messages = [
        "Hey there!",
        "My name is Alice and I work at TechCorp.",
        "I like to code in Python.",
        "This is just a filler message.",
        "I prefer Dark mode UI",
        "Okay bye",
    ]

    # Post chat messages and let ECE_Core store memories automatically
    for m in messages:
        session.post(f"{ece_url.rstrip('/')}/chat", json={"session_id": "bench_salience", "message": m}, timeout=10)

    # Query for saved memories with tag or content
    r = session.get(f"{ece_url.rstrip('/')}/memories/search", params={"tags": "alice, employment"}, timeout=10)
    r.raise_for_status()
    results = r.json().get("memories", [])
    return results


# memlayer removed from the benchmark; functions related to memlayer are intentionally omitted.


def save_results(results: List[Dict[str, Any]], out_path: str):
    # save as JSON and CSV
    json_path = os.path.join(RESULTS_DIR, out_path + ".json")
    csv_path = os.path.join(RESULTS_DIR, out_path + ".csv")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # CSV: flatten raw_memories/traces as counts
    with open(csv_path, "w", newline='', encoding="utf-8") as csvfile:
        if not results:
            return
        keys = [k for k in results[0].keys() if k not in ("raw_memories", "trace", "response_text")]
        writer = csv.DictWriter(csvfile, fieldnames=list(keys) + ["latency_ms"])
        writer.writeheader()
        for r in results:
            row = {k: v for k, v in r.items() if k in keys}
            row["latency_ms"] = r.get("latency_ms")
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ece-url", default="http://localhost:8000", help="ECE_Core URL")
    args = parser.parse_args()

    testcases = load_testcases()

    ece_results = run_ece_tests(args.ece_url, testcases)
    save_results(ece_results, "ece_results")
    print("ECE_Core results saved to benchmarks/results/ece_results.json/csv")

    # Simple summary print for ECE_Core only
    combined = ece_results
    summary = {}
    for r in combined:
        sys = r["system"]
        s = summary.setdefault(sys, {"queries": 0, "found": 0, "total_latency_ms": 0.0})
        s["queries"] += 1
        if r["found"]:
            s["found"] += 1
        s["total_latency_ms"] += r["latency_ms"]

    for sys, stat in summary.items():
        print(f"{sys}: {stat['found']}/{stat['queries']} recall, avg latency {stat['total_latency_ms'] / (stat['queries'] or 1):.1f} ms")


if __name__ == "__main__":
    main()
