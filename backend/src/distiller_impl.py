"""Canonical Distiller implementation used across ECE_Core.

This implementation provides a compact Distiller API that mirrors the
legacy summarization and entity extraction methods used in earlier versions: `distill_moment`,
`annotate_chunk`, `filter_and_consolidate`, `make_compact_summary`, and
validation helpers. The file is intentionally single-copy, deterministic,
and has minimal dependencies to simplify testing.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from collections import OrderedDict
import hashlib as _hashlib
import json as _json
from typing import Tuple

_redis_client = None
_redis_connect_lock = asyncio.Lock()

from pydantic import BaseModel, Field, ValidationError, validator
from src.config import settings
from src.content_utils import clean_content, has_technical_signal, is_token_soup, sanitize_token_soup, normalize_technical_content

logger = logging.getLogger(__name__)

# Simple in-memory distillation cache to avoid repeated LLM calls during ingestion
_distill_cache: "OrderedDict[str, Any]" = OrderedDict()
_distill_cache_limit = 4096
_llm_semaphore: Optional[asyncio.Semaphore] = None


class DistilledEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    type: Optional[str] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("text")
    def not_empty_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Entity text must be non-empty")
        return v.strip()


class DistilledMoment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    summary: Optional[str] = None
    entities: List[DistilledEntity] = Field(default_factory=list)
    score: float = Field(default=0.5, description="Salience score (0.0-1.0)")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("text")
    def not_empty_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Moment text must be non-empty")
        return v.strip()


def _normalize_entity_dict(e: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(e, dict):
        return {}
    if "text" not in e and "name" in e:
        e = dict(e)
        e["text"] = e.pop("name")
    return e


def _simple_entity_extraction(text: str, max_entities: int = 10) -> List[DistilledEntity]:
    # Add technical entity extraction if a technical signal exists
    from src.content_utils import has_technical_signal
    entities: List[DistilledEntity] = []
    seen = set()
    if has_technical_signal(text):
        # extract version numbers, file paths, package names, and error codes
        version_re = re.compile(r'v\d+\.\d+(?:\.\d+)?')
        path_re = re.compile(r'\b(?:[A-Za-z0-9\-_/\\]+\/[A-Za-z0-9\-_.]+)\b')
        pkg_re = re.compile(r'\b(?:npm|pip|apt-get|docker|cargo)\b', re.IGNORECASE)
        for m in version_re.findall(text):
            key = m.lower()
            if key not in seen:
                seen.add(key)
                entities.append(DistilledEntity(text=m, type='version'))
        for m in path_re.findall(text):
            key = m.lower()
            if key not in seen:
                seen.add(key)
                entities.append(DistilledEntity(text=m, type='path'))
        for m in pkg_re.findall(text):
            key = m.lower()
            if key not in seen:
                seen.add(key)
                entities.append(DistilledEntity(text=m, type='package'))
        # also fallback to proper nouns
        pattern = r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
        matches = re.findall(pattern, text)
        for m in matches:
            k = m.strip().lower()
            if k in seen:
                continue
            seen.add(k)
            entities.append(DistilledEntity(text=m, type='proper_noun'))
        return entities[:max_entities]
    pattern = r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
    matches = re.findall(pattern, text)
    out: List[DistilledEntity] = []
    for m in matches:
        key = m.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(DistilledEntity(text=m, type="proper_noun"))
        if len(out) >= max_entities:
            break
    return out


async def _maybe_await(v: Any) -> Any:
    if asyncio.iscoroutine(v):
        return await v
    return v


class Distiller:
    def __init__(self, llm_client: Optional[Any] = None):
        self.llm = llm_client

    async def _call_llm(self, text: str, skip_chunking: bool = False, max_entities: int = 10) -> Any:
        if not self.llm:
            raise RuntimeError("No LLM configured")
        global _llm_semaphore
        if _llm_semaphore is None:
            _llm_semaphore = asyncio.Semaphore(getattr(settings, 'llm_concurrency', 4))
        # Prefer the `generate` API when present (modern LLMs), but support `complete`
        # for legacy clients. Also ensure we use callable attributes (MagicMock
        # will report attributes even when not set). This prevents calling
        # auto-generated MagicMock attributes which return a MagicMock instance
        # rather than the configured AsyncMock return value.
        try:
            if hasattr(self.llm, "generate") and callable(getattr(self.llm, "generate", None)):
                # Allow LLM client to optionally force remote API usage; we rely on the LLM client
                # to raise ContextSizeExceededError when it determines the prompt would exceed server context
                async with _llm_semaphore:
                    return await _maybe_await(self.llm.generate(text))
            if hasattr(self.llm, "complete") and callable(getattr(self.llm, "complete", None)):
                return await _maybe_await(self.llm.complete(text))
        except Exception as e:
            # If the LLM indicates the context is too large and we have not yet chunked, perform chunking
            from src.llm import ContextSizeExceededError
            if isinstance(e, ContextSizeExceededError) and not skip_chunking:
                logger.debug("LLM reported ContextSizeExceeded; falling back to chunk-and-merge strategy")
                return await self._chunk_and_distill(text, max_entities=max_entities)
            raise
        # If we reach here, LLM didn't have expected interface
        raise RuntimeError("LLM missing expected method")
        raise RuntimeError("LLM missing expected method")

    async def distill_moment(self, text: str, chunk_index: Optional[int] = None, total_chunks: Optional[int] = None, max_entities: int = 10, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("text must be non-empty")
        # Keep a copy of the raw text for potential normalizations
        raw_text = text
        # Clean text before distillation while preserving technical signals
        tech = has_technical_signal(text)
        if tech:
            # Preserve technical artifacts, but reduce obvious noise and annotate context
            text = clean_content(text, remove_emojis=False, remove_non_ascii=False, annotate_technical=True)
        else:
            text = clean_content(text, remove_emojis=True, remove_non_ascii=False, annotate_technical=False)
        # Detect token-soup/corrupted content, attempt normalization, then fallback to sanitize
        if is_token_soup(text):
            logger.warning("Detected token-soup content; attempting normalization to preserve technical context")
            # Attempt to normalize technical content (map ANSI, paths, and hex dumps to human tags) and retry
            try:
                normalized = normalize_technical_content(raw_text)
                cleaned_normalized = clean_content(normalized, remove_emojis=False, remove_non_ascii=False)
            except Exception as e:
                logger.debug(f"Normalization failed: {e}")
                cleaned_normalized = ''
            # If normalization produced a non-soup text, proceed with it
            if cleaned_normalized and not is_token_soup(cleaned_normalized):
                text = cleaned_normalized
            else:
                # Keep technical content if flagged; otherwise sanitize aggressively
                sanitized = text if tech else sanitize_token_soup(text)
                # Return a safe fallback summary and minimal entity extraction
                entities = _simple_entity_extraction(sanitized, max_entities=max_entities)
                summary = (sanitized[:300] + '...') if len(sanitized) > 300 else sanitized
                moment = DistilledMoment(text=sanitized, summary=summary, entities=entities, score=0.1)
                return moment.dict()
        entities: List[DistilledEntity] = []
        summary: Optional[str] = None
        if not self.llm:
            return {"summary": text[:200] + "...", "entities": []}
        # Check cache before calling LLM (avoid repeated distillations during ingestion)
        try:
            # Include metadata in the hash so that different metadata results can be cached separately
            content_hash = _hashlib.sha256((text + _json.dumps(metadata or {}, sort_keys=True)).encode('utf-8')).hexdigest()
            cached = _distill_cache.get(content_hash)
            if cached:
                return cached
        except Exception:
            pass
        # Use metadata heuristics to avoid LLM calls for code/log-like artifacts
        try:
            md_path = (metadata or {}).get('path') if isinstance(metadata, dict) else None
            if md_path and isinstance(md_path, str):
                lower = md_path.lower()
                if lower.endswith(('.py', '.js', '.ts', '.java', '.go', '.rs', '.c', '.cpp', '.sh', '.md', '.log')) or '/logs/' in lower or lower.endswith('.log'):
                    entities = _simple_entity_extraction(text, max_entities=max_entities)
                    summary = (text[:400] + '...') if len(text) > 400 else text
                    moment = DistilledMoment(text=text, summary=summary, entities=entities, score=0.1)
                    return moment.dict()
        except Exception:
            pass
        try:
            raw = await self._call_llm(text, max_entities=max_entities)
            parsed = None
            if isinstance(raw, dict):
                parsed = raw
            elif isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    return {"summary": f"Error distilling chunk {chunk_index}. Raw: {str(raw)[:100]}...", "entities": []}
            if isinstance(parsed, dict):
                summary = parsed.get("summary") or parsed.get("title")
                score = float(parsed.get("score", 0.5))
                # Normalize score if 0-10
                if score > 1.0:
                    score = score / 10.0
                
                raw_entities = parsed.get("entities", [])
                for e in raw_entities[:max_entities]:
                    if isinstance(e, str):
                        entities.append(DistilledEntity(text=e))
                    elif isinstance(e, dict):
                        nd = _normalize_entity_dict(e)
                        try:
                            entities.append(DistilledEntity(**nd))
                        except ValidationError:
                            logger.debug("Invalid LLM entity: %s", e)
        except Exception:
            logger.exception("LLM call failed; falling back to simple extractor")
        if not entities:
            entities = _simple_entity_extraction(text, max_entities=max_entities)
            score = 0.5  # Default for fallback
            
        moment = DistilledMoment(text=text, summary=summary, entities=entities, score=score)
        # Write to in-memory cache with limited size
        try:
            _distill_cache[content_hash] = moment.dict()
            if len(_distill_cache) > _distill_cache_limit:
                # pop the oldest
                _distill_cache.popitem(last=False)
        except Exception:
            pass
        return moment.dict()

    async def _chunk_and_distill(self, text: str, max_entities: int = 10) -> Dict[str, Any]:
        """
        Chunk a large piece of text into smaller pieces and distill them individually, then combine summaries.
        This is a simple approach: summarize each chunk, collect summaries, then ask the LLM to summarize the summaries.
        """
        # Detect token-soup/corrupt content and attempt normalization before sanitizing
        if is_token_soup(text):
            logger.warning("Detected token-soup in _chunk_and_distill; attempting normalization")
            try:
                normalized = normalize_technical_content(text)
                cleaned_normalized = clean_content(normalized, remove_emojis=False, remove_non_ascii=False)
            except Exception as e:
                logger.debug(f"Normalization error in _chunk_and_distill: {e}")
                cleaned_normalized = ''
            if cleaned_normalized and not is_token_soup(cleaned_normalized):
                text = cleaned_normalized
            else:
                logger.warning("Normalization did not yield clean text; sanitizing token soup and returning fallback")
                sanitized = sanitize_token_soup(text)
                entities = _simple_entity_extraction(sanitized, max_entities=max_entities)
                summary = (sanitized[:300] + '...') if len(sanitized) > 300 else sanitized
                return {"summary": summary, "entities": [e.dict() for e in entities], "score": 0.1}

        # Estimate tokens and char conversion heuristic (approx 4 chars per token)
        # Prefer to use a chunk size that's smaller than the server context if we detected it
        chunk_tokens = settings.archivist_chunk_size
        if hasattr(self.llm, '_detected_server_context_size') and self.llm._detected_server_context_size:
            try:
                detected = int(self.llm._detected_server_context_size)
                # leave a buffer for prompt and final summary
                usable = max(256, detected - 512)
                if usable < chunk_tokens:
                    chunk_tokens = usable
            except Exception:
                pass
        overlap_tokens = settings.archivist_overlap
        chars_per_token = 4
        chunk_chars = chunk_tokens * chars_per_token
        overlap_chars = overlap_tokens * chars_per_token
        text_len = len(text)
        chunks = []
        start = 0
        while start < text_len:
            end = min(start + chunk_chars, text_len)
            # Try to split at newline within the window for semantic boundaries
            seg = text[start:end]
            if end < text_len:
                last_newline = seg.rfind('\n')
                if last_newline > int(chunk_chars * 0.5):
                    end = start + last_newline
                    seg = text[start:end]
            chunks.append(seg)
            # Advance, with overlap
            start = max(0, end - overlap_chars)
        logger.info(f"Chunked text into {len(chunks)} parts for distillation")
        # Distill each chunk
        chunk_summaries = []
        chunk_entities = []
        for i, c in enumerate(chunks):
            try:
                res = await self._call_llm(c, skip_chunking=True, max_entities=max_entities)
            except Exception as e:
                logger.warning(f"Failed to distill chunk {i} independently: {e}")
                continue
            parsed = None
            if isinstance(res, dict):
                parsed = res
            elif isinstance(res, str):
                try:
                    parsed = json.loads(res)
                except Exception:
                    parsed = {"summary": res}
            if isinstance(parsed, dict):
                chunk_summaries.append(parsed.get("summary") or parsed.get("text") or "")
                raw_entities = parsed.get("entities", []) or []
                for e in raw_entities:
                    if isinstance(e, dict):
                        nd = _normalize_entity_dict(e)
                        try:
                            chunk_entities.append(DistilledEntity(**nd))
                        except ValidationError:
                            logger.debug("Invalid LLM entity in chunk: %s", e)
                    elif isinstance(e, str):
                        chunk_entities.append(DistilledEntity(text=e))
        # Join summaries and ask for final summarization
        combined = "\n\n".join([s for s in chunk_summaries if s])
        # Build a compact instruction for final summarization
        final_prompt = f"Summarize the following chunk summaries into a concise JSON object with fields 'summary' and 'entities'. Summaries:\n\n{combined}"
        final_raw = await self._call_llm(final_prompt, skip_chunking=True, max_entities=max_entities)
        final_parsed = None
        if isinstance(final_raw, dict):
            final_parsed = final_raw
        elif isinstance(final_raw, str):
            try:
                final_parsed = json.loads(final_raw)
            except Exception:
                final_parsed = {"summary": final_raw}
        # Consolidate entities from chunk_entities and final_parsed entities
        entities = []
        if isinstance(final_parsed, dict):
            raw_entities = final_parsed.get("entities", []) or []
            for e in raw_entities:
                if isinstance(e, dict):
                    nd = _normalize_entity_dict(e)
                    try:
                        entities.append(DistilledEntity(**nd))
                    except ValidationError:
                        logger.debug("Invalid final entity: %s", e)
                elif isinstance(e, str):
                    entities.append(DistilledEntity(text=e))
        # Merge chunk_entities
        entities.extend(chunk_entities)
        entities = filter_and_consolidate(entities)
        summary = (final_parsed.get("summary") if isinstance(final_parsed, dict) else final_parsed.get("title") if isinstance(final_parsed, dict) else None) or (combined[:400] + '...')
        # Score: fallback average or default
        score = float(final_parsed.get("score", 0.5)) if isinstance(final_parsed, dict) and final_parsed.get("score") else 0.5
        return {"summary": summary, "entities": [e.dict() for e in entities], "score": score}

    async def annotate_chunk(self, text: str, chunk_number: Optional[int] = None, total_chunks: Optional[int] = None) -> str:
        moment = await self.distill_moment(text, chunk_index=chunk_number, total_chunks=total_chunks)
        entities = moment.get("entities", []) if isinstance(moment, dict) else moment.entities
        summary = moment.get("summary") if isinstance(moment, dict) else moment.summary
        ent_names = [e.get("text") if isinstance(e, dict) else e.text for e in entities]
        ent_str = ", ".join([n for n in ent_names if n])
        return (summary or text[:200]) + ("\n\nEntities: " + ent_str if ent_str else "")

    async def filter_and_consolidate(self, query: str, memories: List[Dict[str, Any]], summaries: List[Dict[str, Any]], active_turn: Optional[str] = None, active_context: Optional[str] = None) -> Dict[str, Any]:
        # Support both active_turn and active_context keywords (legacy vs new callers)
        active_turn = active_turn or active_context
        q_lower = (query or "").lower()
        # Also ensure we strip out test/dev/thinking content that may have slipped into memories
        def _is_memory_clean(m: dict) -> bool:
            if not m or not isinstance(m, dict):
                return False
            meta = m.get('metadata') or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            src = (meta.get('source') or meta.get('path') or '')
            if isinstance(src, str) and any(x in src.lower() for x in ('combined_text', 'prompt-logs', 'calibration_run', 'dry-run')):
                return False
            content = (m.get('content') or '')
            if isinstance(content, str) and ('thinking_content' in content or '[planner]' in content.lower()):
                return False
            return True

        relevant_memories = [m for m in (memories or []) if q_lower in (m.get("content", "") or "").lower() and _is_memory_clean(m)]
        # Preserve active context in output (maintain key for ContextManager)
        return {"summaries": summaries or [], "relevant_memories": relevant_memories, "active_context": active_turn or ""}

    async def make_compact_summary(self, memories: List[Dict[str, Any]], summaries: List[Dict[str, Any]], active_turn: Optional[str], new_input: Optional[str], max_sentences: int = 3) -> str:
        if new_input and new_input.strip():
            return new_input.strip()
        if summaries:
            texts = [s.get("summary") or s.get("text") for s in summaries]
            joined = " ".join([t for t in texts if t])
            sentences = re.split(r"(?<=[.!?])\s+", joined)
            return " ".join([s.strip() for s in sentences if s.strip()][:max_sentences])
        if memories:
            texts = [m.get("content") for m in memories if m.get("content")]
            joined = " ".join(texts)
            sentences = re.split(r"(?<=[.!?])\s+", joined)
            return " ".join([s.strip() for s in sentences if s.strip()][:max_sentences])
        return ""

    def _safe_validate_moment(self, moment_data: Dict[str, Any]) -> DistilledMoment:
        return DistilledMoment(**moment_data)


def filter_and_consolidate(entities: Iterable[DistilledEntity]) -> List[DistilledEntity]:
    by_key: Dict[str, DistilledEntity] = {}
    for e in entities:
        if not e or not e.text:
            continue
        key = e.text.strip().lower()
        existing = by_key.get(key)
        if not existing:
            by_key[key] = e
            continue
        if (existing.score or 0) < (e.score or 0):
            by_key[key] = e
    return list(by_key.values())


def make_compact_summary(moment: DistilledMoment, max_sentences: int = 3) -> str:
    if moment.summary and moment.summary.strip():
        return moment.summary.strip()
    sentences = re.split(r"(?<=[.!?])\s+", moment.text)
    return " ".join([s.strip() for s in sentences if s.strip()][:max_sentences])


_default_distiller = Distiller()


async def distill_moment(text: str, llm_client: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    """Global convenience function. Accepts metadata to help Distiller choose strategy.
    If a Redis cache is configured, the function will attempt to reuse distillation results.
    """
    d = _default_distiller if llm_client is None else Distiller(llm_client)
    # If Redis caching enabled, try to fetch first
    try:
        if getattr(settings, 'memory_distill_cache_enabled', False) and getattr(settings, 'redis_url', None):
            global _redis_client
            async with _redis_connect_lock:
                if _redis_client is None:
                    try:
                        import redis.asyncio as aioredis
                        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
                        await _redis_client.ping()
                    except Exception:
                        _redis_client = None
            if _redis_client is not None:
                key = _hashlib.sha256((text + _json.dumps(metadata or {}, sort_keys=True)).encode('utf-8')).hexdigest()
                try:
                    val = await _redis_client.get(key)
                    if val:
                        # parse and return
                        return _json.loads(val)
                except Exception:
                    # Ignore Redis errors and fall back to in-memory cache
                    pass
    except Exception:
        pass
    result = await d.distill_moment(text, metadata=metadata, **kwargs)
    # Cache to Redis + in-memory cache if enabled
    try:
        content_hash = _hashlib.sha256((text + _json.dumps(metadata or {}, sort_keys=True)).encode('utf-8')).hexdigest()
        _distill_cache[content_hash] = result
        if len(_distill_cache) > _distill_cache_limit:
            _distill_cache.popitem(last=False)
        if getattr(settings, 'memory_distill_cache_enabled', False) and getattr(settings, 'redis_url', None) and _redis_client:
            try:
                await _redis_client.set(content_hash, _json.dumps(result), ex=getattr(settings, 'memory_distill_cache_ttl', 86400))
            except Exception:
                pass
    except Exception:
        pass
    return result


async def annotate_chunk(text: str, llm_client: Optional[Any] = None, **kwargs: Any) -> str:
    d = _default_distiller if llm_client is None else Distiller(llm_client)
    return await d.annotate_chunk(text, **kwargs)


def _safe_validate_moment(moment_data: Dict[str, Any]) -> DistilledMoment:
    return _default_distiller._safe_validate_moment(moment_data)


__all__ = [
    "DistilledEntity",
    "DistilledMoment",
    "Distiller",
    "distill_moment",
    "annotate_chunk",
    "_safe_validate_moment",
    "filter_and_consolidate",
    "make_compact_summary",
]
