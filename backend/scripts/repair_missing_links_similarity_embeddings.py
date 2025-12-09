from scripts.neo4j.repair.repair_missing_links_similarity_embeddings import *


async def embed_texts(client: LLMClient, texts: list[str]):
    # returns list of embeddings
    # Use per-document chunking helper to avoid server errors on long inputs
    # Use the client's default chunk_size logic; callers may pass a chunk_size arg themselves
    embs = await client.get_embeddings_for_documents(texts)
    return embs


def cosine(a, b):
    if not a or not b:
        return 0.0
    # dot / (norm * norm)
    dot = 0.0
    sa = 0.0
    sb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        sa += x * x
        sb += y * y
    if sa == 0 or sb == 0:
        return 0.0
    return dot / (math.sqrt(sa) * math.sqrt(sb))


def remove_html_tags(text: str) -> str:
    return re.sub(r'<[^>]+>', ' ', text)


EMOJI_REGEX = re.compile(
    "[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    return EMOJI_REGEX.sub('', text)


def extract_text_from_json(content: str) -> str:
    # Try to parse JSON and extract first text-like field (response_content, content, text)
    try:
        obj = json.loads(content)
        # If dict, try common fields
        if isinstance(obj, dict):
            for k in ('response_content', 'content', 'text', 'message', 'response'):
                if k in obj and isinstance(obj[k], str):
                    return obj[k]
            # fallback: flatten dict values
            values = []
            for v in obj.values():
                if isinstance(v, str):
                    values.append(v)
            return ' '.join(values)
        if isinstance(obj, list):
            texts = []
            for el in obj:
                if isinstance(el, dict):
                    for k in ('response_content', 'content', 'text'):
                        if k in el and isinstance(el[k], str):
                            texts.append(el[k])
                elif isinstance(el, str):
                    texts.append(el)
            return ' '.join(texts)
    except Exception:
        return content
    return content


def clean_content(text: str, remove_emojis=True, remove_non_ascii=False) -> str:
    if not text:
        return ''
    # If content appears to be JSON, try to extract text fields
    t = text.strip()
    if t.startswith('{') or t.startswith('[') or '"response_content"' in t:
        t2 = extract_text_from_json(t)
        if isinstance(t2, str) and t2:
            t = t2
    # remove HTML tags
    t = remove_html_tags(t)
    # unescape HTML entities
    t = html.unescape(t)
    # strip emojis if desired
    if remove_emojis:
        t = strip_emojis(t)
    # optionally remove non-ascii characters (disabled by default to not lose other languages)
    if remove_non_ascii:
        t = ''.join([c for c in t if ord(c) < 128])
    # remove long sequences of punctuation and collapse whitespace
    t = re.sub(r'[^\w\s\.,;:\-\'"@#%\(\)\?\/\\]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def is_json_like(text: str) -> bool:
    if not text:
        return False
    patterns = [r"\{\s*\".*\"\s*:\s*", r"\[\s*\{", r'"response_content"', r'"timestamp"']
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def is_html_like(text: str) -> bool:
    if not text:
        return False
    patterns = [r'<\s*\/?\w+[^>]*>', r'<a\s+href=', r'<script\b', r'<div\b', r'<p\b']
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def append_csv(path, header, rows):
    write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
    with open(path, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(header)
        for row in rows:
            w.writerow(row)


async def run_repair(window_async=False, threshold=0.75, limit=100, candidate_limit: int | None = None, dry_run=True, csv_out=None, batch_size: int | None = None, min_batch=1, embed_delay=0.15, embed_retries=3, emb_max_chars: int | None = None, top_n=1, skip_json=True, skip_html=True, min_clean_length=30, min_origin_length=100, time_window_hours=None, prefer_same_app=False, require_same_app=False, delta=None, max_commit=None, commit=False, exclude_phrases=None, skip=0, run_id: str = None):
    s = Settings()
    # use configured default if CLI didn't provide emb_max_chars
    from src.config import settings as global_settings
    if emb_max_chars is None:
        emb_max_chars = global_settings.llm_embeddings_chunk_size_default
    if candidate_limit is None:
        candidate_limit = global_settings.weaver_candidate_limit
    if batch_size is None:
        batch_size = getattr(global_settings, 'weaver_batch_size_default', global_settings.llm_embeddings_default_batch_size)
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return

    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    llm = LLMClient()

    created = 0
    committed = 0
    if commit:
        dry_run = False
    processed = 0
    # Additional audit fields (run_id, second_score, delta_diff, num_candidates, commit_ts)
    header = ['run_id','s_eid', 's_app_id', 's_created_at', 'orig_eid', 'orig_app_id', 'orig_created_at', 'score', 'second_score', 'delta_diff', 'num_candidates', 'method', 'status', 'error', 's_excerpt', 'orig_excerpt', 'commit_ts']

    async with asyncio.Semaphore(4):
        pass

    # Generate run_id for traceability (can be supplied via CLI override)
    if not run_id:
        run_id = str(uuid.uuid4())
    print(f"Run ID: {run_id}")

    with driver.session() as session:
        results = session.run("""
            MATCH (s:Memory)
            WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->()
            RETURN elementId(s) as s_eid, s.app_id as s_app_id, s.created_at as s_created_at, s.content as content, s.content_cleaned as content_cleaned
            ORDER BY s.created_at DESC
            SKIP $skip
            LIMIT $limit
            """, {'limit': limit, 'skip': skip})
        summaries = list(results)
        print(f"Processing {len(summaries)} summaries (embedding-based); dry_run={dry_run}")

        for sr in summaries:
            processed += 1
            s_eid = sr['s_eid']
            s_app_id = sr.get('s_app_id')
            s_content = sr.get('content') or ''
            # Candidate generation: use token length heuristics as earlier
            # Try to use metadata token count if present
            s_meta = {}
            try:
                s_meta = json.loads(sr['metadata']) if sr['metadata'] else {}
            except Exception:
                s_meta = {}
            s_tok = s_meta.get('original_token_count') or s_meta.get('token_count')
            candidates_query = None
            params = {}
            if s_tok:
                try:
                    st = int(s_tok)
                    est_chars = st * 4
                    min_chars = int(max(200, est_chars * 0.5))
                    max_chars = int(est_chars * 1.6)
                    candidates_query = """
                        MATCH (orig:Memory)
                        WHERE (orig.category IS NULL OR orig.category <> 'summary')
                          AND size(orig.content) >= $min_chars AND size(orig.content) <= $max_chars
                        RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content
                        LIMIT $candidate_limit
                    """
                    params = {'min_chars': min_chars, 'max_chars': max_chars, 'candidate_limit': candidate_limit}
                except Exception:
                    candidates_query = None
            # If time_window_hours provided, filter by created_at window
            if time_window_hours and sr.get('s_created_at'):
                try:
                    s_created_str = sr.get('s_created_at')
                    s_dt = datetime.fromisoformat(s_created_str)
                    time_window_delta = timedelta(hours=int(time_window_hours))
                    min_dt = (s_dt - time_window_delta).isoformat()
                    max_dt = (s_dt + time_window_delta).isoformat()
                    # if prefer_same_app: combine same-app candidates first then others
                    if require_same_app and sr.get('s_app_id'):
                        candidates_query = """
                            MATCH (orig:Memory)
                            WHERE (orig.category IS NULL OR orig.category <> 'summary')
                              AND datetime(orig.created_at) >= datetime($min_dt) AND datetime(orig.created_at) <= datetime($max_dt)
                              AND orig.app_id = $s_app_id
                            RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content, orig.content_cleaned as content_cleaned
                            LIMIT $candidate_limit
                        """
                        params = {'min_dt': min_dt, 'max_dt': max_dt, 'candidate_limit': candidate_limit, 's_app_id': sr.get('s_app_id')}
                    else:
                        # prefer_same_app: fetch same-app candidate subset first
                        if prefer_same_app and sr.get('s_app_id'):
                            # We'll fetch same-app subset up to half limits and then others (later captured in code)
                            # Build a general query; we'll combine results from two queries below.
                            candidates_query = "MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') AND datetime(orig.created_at) >= datetime($min_dt) AND datetime(orig.created_at) <= datetime($max_dt) RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content, orig.content_cleaned as content_cleaned LIMIT $candidate_limit"
                        else:
                            candidates_query = "MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') AND datetime(orig.created_at) >= datetime($min_dt) AND datetime(orig.created_at) <= datetime($max_dt) RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content, orig.content_cleaned as content_cleaned LIMIT $candidate_limit"
                        params = {'min_dt': min_dt, 'max_dt': max_dt, 'candidate_limit': candidate_limit}
                except Exception:
                    # fallback to generic query
                    candidates_query = None
                    params = {}
            if not candidates_query:
                candidates_query = "MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content, orig.content_cleaned as content_cleaned LIMIT $candidate_limit"
                params = {'candidate_limit': candidate_limit}

            # If prefer_same_app is set, and time_window_hours applied, then do two queries
            candidates = []
            if prefer_same_app and time_window_hours and sr.get('s_app_id') and sr.get('s_created_at'):
                # First: same app candidates in time window up to half limit
                half = int(candidate_limit / 2)
                q_same = "MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') AND datetime(orig.created_at) >= datetime($min_dt) AND datetime(orig.created_at) <= datetime($max_dt) AND orig.app_id = $s_app_id RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content, orig.content_cleaned as content_cleaned LIMIT $half"
                params_same = {'min_dt': min_dt, 'max_dt': max_dt, 'half': half, 's_app_id': sr.get('s_app_id')}
                cres_same = session.run(q_same, {'min_dt': min_dt, 'max_dt': max_dt, 'half': half, 's_app_id': sr.get('s_app_id')})
                candidates += [r for r in cres_same]
                if len(candidates) < candidate_limit:
                    # Fill the remainder with other app candidates in same time window
                    remaining = candidate_limit - len(candidates)
                    q_other = "MATCH (orig:Memory) WHERE (orig.category IS NULL OR orig.category <> 'summary') AND datetime(orig.created_at) >= datetime($min_dt) AND datetime(orig.created_at) <= datetime($max_dt) AND (orig.app_id IS NULL OR orig.app_id <> $s_app_id) RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at, orig.content as content, orig.content_cleaned as content_cleaned LIMIT $remaining"
                    cres_other = session.run(q_other, {'min_dt': min_dt, 'max_dt': max_dt, 'remaining': remaining, 's_app_id': sr.get('s_app_id')})
                    candidates += [r for r in cres_other]
            else:
                cres = session.run(candidates_query, params)
                candidates = [r for r in cres]
            if not candidates:
                continue

            # Compute embeddings
            # We'll compute one embedding for the summary and batch embeddings for all candidates
            try:
                # Optionally skip JSON/HTML-like summary nodes
                if skip_json and is_json_like(s_content or ''):
                    print(f"⚠️  Skipping summary {s_eid} (json-like content)")
                    if dry_run and csv_out:
                        append_csv(csv_out, header, [[str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), '', '', '', '', '', '', '', 'similarity_emb', 'skipped_json_summary', '', (s_content or '')[:200], '', '']])
                    continue
                if skip_html and is_html_like(s_content or ''):
                    print(f"⚠️  Skipping summary {s_eid} (html-like content)")
                    if dry_run and csv_out:
                        append_csv(csv_out, header, [[str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), '', '', '', '', '', '', '', 'similarity_emb', 'skipped_html_summary', '', (s_content or '')[:200], '', '']])
                    continue
                # Clean content prior to embedding
                    # Prefer cleaned content property if present
                # Prefer cleaned content property if present
                if sr.get('content_cleaned'):
                    s_content = sr.get('content_cleaned')
                else:
                    s_content = clean_content(s_content or '', remove_emojis=True, remove_non_ascii=False)
                # use chunking+averaging helper to embed long summaries rather than truncating
                s_text_to_embed = (s_content or '')
                s_embs = await llm.get_embeddings_for_documents([s_text_to_embed], chunk_size=emb_max_chars, batch_size=batch_size, min_batch=min_batch, delay=embed_delay, max_retries=embed_retries)
                s_emb = s_embs[0] if s_embs and len(s_embs) > 0 else None
                if not s_emb:
                    print(f"⚠️  Empty summary embedding for {s_eid}, skipping")
                    if dry_run and csv_out:
                        s_excerpt = (s_content or '')[:200]
                        row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), '', '', '', '', '', '', '', 'similarity_emb', 's_emb_failed', 'empty_summary_embedding', s_excerpt, '', '']
                        append_csv(csv_out, header, [row])
                    continue
            except Exception as e:
                print(f"Failed to embed summary {s_eid}: {e}")
                continue

            # Batch candidate contents (truncate long texts to avoid server errors)
            # Clean candidate contents and only keep those with non-empty cleaned text
            cleaned_candidates = []
            for r in candidates:
                # Optionally skip JSON/HTML candidate records
                raw_candidate_text = r.get('content_cleaned') if r.get('content_cleaned') else (r.get('content') or '')
                if skip_json and is_json_like(raw_candidate_text):
                    continue
                if skip_html and is_html_like(raw_candidate_text):
                    continue
                c_text = clean_content(raw_candidate_text, remove_emojis=True, remove_non_ascii=False)
                # Apply optional min-origin-length filter to avoid hub nodes and low-information origins
                if not c_text or len(c_text) < (min_origin_length or 30):
                    # skip short/empty cleaned text
                    continue
                # Filter out generic hub phrases
                skip_phrase = False
                if exclude_phrases:
                    for ph in exclude_phrases:
                        if ph and ph.strip().lower() in c_text.lower():
                            skip_phrase = True
                            break
                if skip_phrase:
                    continue
                cleaned_candidates.append((r, c_text))
            if not cleaned_candidates:
                # nothing to embed
                if csv_out and dry_run:
                    s_excerpt = (s_content or '')[:200]
                    row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), '', '', '', '', '', '', '', 'similarity_emb', 'no_candidate_after_clean', '', s_excerpt, '', '']
                    append_csv(csv_out, header, [row])
                continue
            candidate_texts = [c for _, c in cleaned_candidates]

            # Use the LLM client's chunking+batching helper to embed candidate texts. This will chunk long items and average per-doc.
            c_embs = await llm.get_embeddings_for_documents(candidate_texts, chunk_size=emb_max_chars, batch_size=batch_size, min_batch=min_batch, delay=embed_delay, max_retries=embed_retries)

            # c_embs already computed via chunk-aware batched embeddings

            # Compute cosine similarities
            best_score = -1.0
            best_idx = None
            # Note: results correspond to cleaned_candidates list
            for i, emb in enumerate(c_embs):
                try:
                    score = cosine(s_emb, emb)
                except Exception:
                    score = 0.0
                if score > best_score:
                    best_score = score
                    best_idx = i

            # Optionally write top_n rows for audit even if not above threshold
            # compute all scores once
            scored_rows = []
            for i, emb in enumerate(c_embs):
                sc = cosine(s_emb, emb) if emb else 0.0
                # candidate reference: cleaned_candidates
                orig_rec, _ = cleaned_candidates[i]
                scored_rows.append((sc, i, orig_rec))

            scored_rows = sorted(scored_rows, key=lambda s: s[0], reverse=True)
            if len(scored_rows) > 0:
                best_score, best_idx, _ = scored_rows[0]
                best = cleaned_candidates[best_idx][0]
                # compute second_score and delta_diff for CSV
                second_score = scored_rows[1][0] if len(scored_rows) > 1 else 0.0
                delta_diff = best_score - second_score
                num_candidates = len(scored_rows)
                # Report to CSV (including status and short excerpts to make audits easier)
                s_excerpt = (s_content or '')[:200]
                orig_excerpt = (best.get('content') or '')[:200]
                row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), str(best['orig_eid']), str(best.get('orig_app_id') if best.get('orig_app_id') else ''), str(best.get('o_created_at') if best.get('o_created_at') else ''), f"{best_score:.4f}", f"{second_score:.4f}", f"{delta_diff:.4f}", str(num_candidates), 'similarity_emb', 'ok', '', s_excerpt, orig_excerpt, '']
                if dry_run:
                    if csv_out:
                        append_csv(csv_out, header, [row])
                    else:
                        print("DRY EMBSIM:", row)
                else:
                    # Only commit relationships if the best score exceeds the configured threshold
                    if best_score < threshold:
                        # Log that we skipped commit due to low confidence
                        if csv_out:
                            low_row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), str(best['orig_eid']), str(best.get('orig_app_id') if best.get('orig_app_id') else ''), str(best.get('o_created_at') if best.get('o_created_at') else ''), f"{best_score:.4f}", f"{second_score:.4f}", f"{delta_diff:.4f}", str(num_candidates), 'similarity_emb', 'below_threshold', '', s_excerpt, orig_excerpt, '']
                            append_csv(csv_out, header, [low_row])
                        else:
                            print(f"Skipping merge for s={s_eid} -> orig={best['orig_eid']} (score={best_score:.4f} < threshold={threshold})")
                        continue
                    # DELTA guard: ensure top score is better than next best by `delta`
                    if delta is not None and len(scored_rows) > 1:
                        second_score = scored_rows[1][0]
                        if (best_score - second_score) < float(delta):
                            if csv_out:
                                append_csv(csv_out, header, [[str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), str(best['orig_eid']), str(best.get('orig_app_id') if best.get('orig_app_id') else ''), str(best.get('o_created_at') if best.get('o_created_at') else ''), f"{best_score:.4f}", f"{second_score:.4f}", f"{delta_diff:.4f}", str(num_candidates), 'similarity_emb', 'below_delta', '', s_excerpt, orig_excerpt, '']])
                            else:
                                print(f"Skipping merge for s={s_eid} -> orig={best['orig_eid']} (score={best_score:.4f} not >= second+delta)")
                            continue

                    # Commit: try to MERGE the relationship and optionally log
                    try:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        # Attach audit properties on the relationship to enable traceability & rollback
                        if best.get('orig_app_id') and s_app_id:
                            session.run(
                                "MATCH (s:Memory{app_id: $s_app}), (orig:Memory{app_id: $orig_app}) MERGE (s)-[r:DISTILLED_FROM]->(orig) ON CREATE SET r.auto_commit_run_id = $run_id, r.auto_commit_score = $score, r.auto_commit_delta = $delta, r.auto_committed_by = $by, r.auto_commit_ts = $now",
                                {'s_app': str(s_app_id), 'orig_app': str(best.get('orig_app_id')), 'run_id': run_id, 'score': best_score, 'delta': float(delta) if delta is not None else None, 'by': 'repair_missing_links_similarity_embeddings', 'now': now_iso}
                            )
                        elif best.get('orig_app_id') and not s_app_id:
                            session.run(
                                "MATCH (s),(orig:Memory{app_id: $orig_app}) WHERE elementId(s) = $s_eid MERGE (s)-[r:DISTILLED_FROM]->(orig) ON CREATE SET r.auto_commit_run_id = $run_id, r.auto_commit_score = $score, r.auto_commit_delta = $delta, r.auto_committed_by = $by, r.auto_commit_ts = $now",
                                {'s_eid': str(s_eid), 'orig_app': str(best.get('orig_app_id')), 'run_id': run_id, 'score': best_score, 'delta': float(delta) if delta is not None else None, 'by': 'repair_missing_links_similarity_embeddings', 'now': now_iso}
                            )
                        else:
                            session.run(
                                "MATCH (s),(orig) WHERE elementId(s) = $s_eid AND elementId(orig) = $orig_eid MERGE (s)-[r:DISTILLED_FROM]->(orig) ON CREATE SET r.auto_commit_run_id = $run_id, r.auto_commit_score = $score, r.auto_commit_delta = $delta, r.auto_committed_by = $by, r.auto_commit_ts = $now",
                                {'s_eid': str(s_eid), 'orig_eid': str(best['orig_eid']), 'run_id': run_id, 'score': best_score, 'delta': float(delta) if delta is not None else None, 'by': 'repair_missing_links_similarity_embeddings', 'now': now_iso}
                            )
                    except Exception as e:
                        print(f"Failed to MERGE relationship for s={s_eid} -> orig={best['orig_eid']}: {e}")
                        # Optionally append a CSV row with failure details
                        if csv_out:
                            s_excerpt = (s_content or '')[:200]
                            orig_excerpt = (best.get('content') or '')[:200]
                            err_row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), str(best['orig_eid']), str(best.get('orig_app_id') if best.get('orig_app_id') else ''), str(best.get('o_created_at') if best.get('o_created_at') else ''), f"{best_score:.4f}", f"{second_score:.4f}", f"{delta_diff:.4f}", str(num_candidates), 'similarity_emb', 'merge_failed', str(e), s_excerpt, orig_excerpt, '']
                            append_csv(csv_out, header, [err_row])
                        continue
                    # If commit succeeded, optionally record success log row
                    if csv_out:
                        # set commit_ts and append
                        row[-1] = now_iso
                        append_csv(csv_out, header, [row])
                    created += 1
                    committed += 1
                    # If a max-commit parameter is specified, stop committing after reaching it
                    if max_commit and committed >= int(max_commit):
                        print(f"Reached max_commit={max_commit} - stopping further commits")
                        # Close driver and return
                        driver.close()
                        return
            else:
                # No match above threshold; write CSV for manual review if requested
                if dry_run and csv_out:
                    # write row showing highest scoring candidate (even if below threshold)
                    if best_idx is not None:
                            maybe = candidates[best_idx]
                            s_excerpt = (s_content or '')[:200]
                            orig_excerpt = (maybe.get('content') or '')[:200]
                            row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), str(maybe['orig_eid']), str(maybe.get('orig_app_id') if maybe.get('orig_app_id') else ''), str(maybe.get('o_created_at') if maybe.get('o_created_at') else ''), f"{best_score:.4f}", f"{second_score:.4f}" if 'second_score' in locals() else '', f"{delta_diff:.4f}" if 'delta_diff' in locals() else '', str(num_candidates) if 'num_candidates' in locals() else str(len(cleaned_candidates)), 'similarity_emb', 'no_match', '', s_excerpt, orig_excerpt, '']
                            append_csv(csv_out, header, [row])
                    # Also optionally append the top N matches for manual inspection
                    if csv_out and top_n > 1:
                        topN = top_n if top_n < len(scored_rows) else len(scored_rows)
                        extras = []
                        for sc, idx, cand in scored_rows[:topN]:
                            s_excerpt = (s_content or '')[:200]
                            orig_excerpt = (cand.get('content') or '')[:200]
                            extra_row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), str(cand['orig_eid']), str(cand.get('orig_app_id') or ''), str(cand.get('o_created_at') or ''), f"{sc:.4f}", f"{second_score:.4f}" if 'second_score' in locals() else '', f"{delta_diff:.4f}" if 'delta_diff' in locals() else '', str(num_candidates) if 'num_candidates' in locals() else str(len(cleaned_candidates)), 'similarity_emb', 'no_match', '', s_excerpt, orig_excerpt, '']
                            extras.append(extra_row)
                        append_csv(csv_out, header, extras)
                    else:
                        # nothing scored at all - possibly an embedding error
                        s_excerpt = (s_content or '')[:200]
                        row = [str(run_id), str(s_eid), str(s_app_id) if s_app_id else '', str(sr.get('s_created_at') if sr.get('s_created_at') else ''), '', '', '', '', '', '', '', 'similarity_emb', 'no_match', 'no_candidates_scored', s_excerpt, '', '']
                        append_csv(csv_out, header, [row])

        print(f"Done: processed={processed}, created={created} (dry_run={dry_run})")
    driver.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Repair missing relationships using LLM embeddings')
    parser.add_argument('--threshold', '-t', default=0.75, type=float, help='Cosine similarity threshold (0-1.0)')
    parser.add_argument('--limit', '-l', default=100, type=int, help='Limit number of summary candidates')
    parser.add_argument('--candidate-limit', '-c', default=None, type=int, help='Limit number of origin candidates per summary')
    parser.add_argument('--dry-run', action='store_true', help='Dry run: do not write DB changes')
    parser.add_argument('--csv-out', type=str, default=None, help='If set, append dry-run candidate pairs to CSV')
    parser.add_argument('--batch-size', default=None, type=int, help='Embedding batch size (reads from .env if not supplied)')
    parser.add_argument('--min-batch', default=1, type=int, help='Minimum embedding batch size (for adaptive shrinking)')
    parser.add_argument('--embed-delay', default=0.15, type=float, help='Delay between embedding requests to avoid hammering the server')
    parser.add_argument('--embed-retries', default=3, type=int, help='Max per-item retries when embedding fails')
    parser.add_argument('--top-n', default=1, type=int, help='Number of top candidate matches to append to CSV for review (1 = only best candidate)')
    parser.add_argument('--emb-max-chars', default=None, type=int, help='Maximum characters to send to embeddings API per text; lower if server errors occur')
    parser.add_argument('--skip-json', action='store_true', help='Skip nodes that look like JSON input')
    parser.add_argument('--skip-html', action='store_true', help='Skip nodes that look like HTML/markup')
    parser.add_argument('--min-clean-length', default=30, type=int, help='Minimum cleaned content length to consider for embedding')
    parser.add_argument('--min-origin-length', default=100, type=int, help='Minimum cleaned content length for origin candidate (filter out hubs)')
    parser.add_argument('--exclude-phrases', default=None, type=str, help='Comma-separated list of phrases to exclude from origin candidates (hub phrases)')
    parser.add_argument('--time-window-hours', default=None, type=int, help='If set, only consider origin candidates within +/- N hours of summary created_at')
    parser.add_argument('--prefer-same-app', action='store_true', help='Prioritize candidates whose app_id matches the summary (prefer within time window)')
    parser.add_argument('--require-same-app', action='store_true', help='Require origin candidates have the same app_id as the summary (hard filter)')
    parser.add_argument('--delta', default=0.05, type=float, help='Top candidate must exceed second-best by this delta (e.g., 0.05)')
    parser.add_argument('--max-commit', default=None, type=int, help='Maximum number of relationships to commit in this run')
    parser.add_argument('--commit', action='store_true', help='If set, perform database commits (otherwise dry-run)')
    parser.add_argument('--skip', default=0, type=int, help='Skip N summaries (useful for batched runs)')
    parser.add_argument('--run-id', default=None, type=str, help='Optional run id to use for this run; otherwise a random uuid is generated')
    args = parser.parse_args()
    exclude_phrases = None
    if args.exclude_phrases:
        exclude_phrases = [p.strip() for p in args.exclude_phrases.split(',') if p.strip()]
    asyncio.run(run_repair(threshold=args.threshold, limit=args.limit, candidate_limit=args.candidate_limit, dry_run=args.dry_run, csv_out=args.csv_out, batch_size=args.batch_size, min_batch=args.min_batch, embed_delay=args.embed_delay, embed_retries=args.embed_retries, emb_max_chars=args.emb_max_chars, top_n=args.top_n, skip_json=args.skip_json, skip_html=args.skip_html, min_clean_length=args.min_clean_length, min_origin_length=args.min_origin_length, time_window_hours=args.time_window_hours, prefer_same_app=args.prefer_same_app, require_same_app=args.require_same_app, delta=args.delta, max_commit=args.max_commit, commit=args.commit, exclude_phrases=exclude_phrases, skip=args.skip, run_id=args.run_id))
