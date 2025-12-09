"""
Simple LLM client supporting both API servers and local GGUF models.

Supports:
- llama.cpp server (OpenAI-compatible API)
- Local GGUF files via llama-cpp-python
- MCP (Model Context Protocol) for reliable tool execution
"""
import httpx
import logging
import asyncio
from typing import Optional, List, Tuple, Dict
import math
from src.config import settings
import os
import re
import json
from src.chat_templates import chat_template_manager

logger = logging.getLogger(__name__)


class EmbeddingsAPIError(RuntimeError):
    """Raised when embedding API responds with an error. Contains parsed info if available.

    Attributes:
        status_code: numeric HTTP status code
        body: raw response body
        server_message: parsed message (if present)
        n_ctx: optional detected context size (tokens)
    """
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None, server_message: Optional[str] = None, n_ctx: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.server_message = server_message
        self.n_ctx = n_ctx


class LLMClient:
    """
    LLM client with automatic fallback:
    1. Try API server (llama.cpp server, LM Studio, etc.)
    2. Fall back to local GGUF loading if API unavailable
    """
    
    def __init__(self):
        # Normalize API base so we don't accidentally double-up /v1 segments
        api_base = settings.llm_api_base or ''
        api_base = api_base.rstrip('/')
        # If the configured base ended in /v1, strip it; we'll append /v1 endpoints below
        if api_base.endswith('/v1'):
            api_base = api_base[:-3]
        self.api_base = api_base
        # Embeddings may use a different base (embedding-only server on 8081). Prefer explicit embeddings base setting, fallback to api_base
        emb_base = getattr(settings, 'llm_embeddings_api_base', '') or settings.llm_api_base
        emb_base = str(emb_base).rstrip('/')
        if emb_base.endswith('/v1'):
            emb_base = emb_base[:-3]
        self.embeddings_base = emb_base
        # Resolve model name defensively to handle different possible config names
        # Some environments may provide either `llm_model_name` or `llm_model`.
        self.model = getattr(settings, 'llm_model_name', getattr(settings, 'llm_model', ''))
        self.model_path = settings.llm_model_path
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout)

        # Chat template configuration
        # Use the resolved template which can auto-detect based on model name
        resolved_template = getattr(settings, 'resolved_chat_template', 'openai')
        self.chat_template_name = resolved_template
        self.chat_template = chat_template_manager.get_template(self.chat_template_name)
        
        # Lazy-load local model if needed
        self._local_llm = None
        self._use_local = False
        self._local_llm_embedding_enabled = False
        self._detected_model = None
        self._model_detection_attempted = False
        # Embeddings-specific detection
        self._detected_embeddings_model = None
        self._embeddings_model_detection_attempted = False
        # Detected server context size (tokens). May be populated by parsing API errors
        self._detected_server_context_size: Optional[int] = None
        # Force remote usage flag (skip local fallback)
        self.force_remote_api: bool = False
    
    async def detect_model(self) -> str:
        """
        Detect the actual model running on the API server.
        Makes a GET request to /v1/models endpoint.
        Returns: Model name or falls back to configured name.
        """
        if self._model_detection_attempted:
            return self._detected_model or self.model
        
        self._model_detection_attempted = True
        
        try:
            # Try to get models list from API
            response = await self.client.get(f"{self.api_base}/models")
            response.raise_for_status()
            result = response.json()
            
            if "data" in result and len(result["data"]) > 0:
                # Get first model or find best match
                models = result["data"]
                if isinstance(models[0], dict) and "id" in models[0]:
                    self._detected_model = models[0]["id"]
                    print(f"✅ Detected model: {self._detected_model}")
                    try:
                        md = models[0]
                        context_keys = ['n_ctx_train', 'n_ctx', 'context', 'context_window', 'max_input_tokens', 'max_context_tokens', 'max_tokens']
                        for ck in context_keys:
                            if ck in md and isinstance(md[ck], int):
                                self._detected_server_context_size = md[ck]
                                print(f"🔎 Detected server context size via model metadata: {self._detected_server_context_size}")
                                break
                    except Exception:
                        pass
                    return self._detected_model
        except Exception as e:
            print(f"⚠️  Model detection failed: {e}")
        
        # Fallback to configured model
        self._detected_model = self.model
        print(f"📋 Using configured model: {self._detected_model}")
        return self._detected_model

    async def detect_embeddings_model(self) -> str:
        """
        Detect the model served by the embeddings base. Falls back to `settings.llm_embeddings_model_name` or general model.
        """
        if self._embeddings_model_detection_attempted:
            return self._detected_embeddings_model or settings.llm_embeddings_model_name or self.model
        self._embeddings_model_detection_attempted = True
        try:
            response = await self.client.get(f"{self.embeddings_base}/models")
            response.raise_for_status()
            result = response.json()
            if "data" in result and len(result["data"]) > 0:
                models = result["data"]
                if isinstance(models[0], dict) and "id" in models[0]:
                    self._detected_embeddings_model = models[0]["id"]
                    # Attempt to parse context window (tokens) from model metadata
                    md = models[0]
                    # Look for typical fields
                    context_keys = [
                        'n_ctx_train', 'n_ctx', 'context', 'context_window', 'max_input_tokens', 'max_context_tokens', 'max_tokens'
                    ]
                    for ck in context_keys:
                        if ck in md and isinstance(md[ck], int):
                            self._detected_server_context_size = md[ck]
                            print(f"🔎 Detected embeddings model context tokens via model metadata: {self._detected_server_context_size}")
                            break
                    # If not found, attempt a details endpoint for the model
                    if not self._detected_server_context_size:
                        try:
                            model_detail_resp = await self.client.get(f"{self.embeddings_base}/models/{self._detected_embeddings_model}")
                            model_detail_resp.raise_for_status()
                            detail_json = model_detail_resp.json()
                            if isinstance(detail_json, dict):
                                for ck in context_keys:
                                    if ck in detail_json and isinstance(detail_json[ck], int):
                                        self._detected_server_context_size = detail_json[ck]
                                        print(f"🔎 Detected embeddings model context tokens via model detail endpoint: {self._detected_server_context_size}")
                                        break
                        except Exception:
                            pass
                    print(f"✅ Detected embeddings model: {self._detected_embeddings_model}")
                    return self._detected_embeddings_model
        except Exception as e:
            print(f"⚠️  Embeddings model detection failed: {e}")
        # Fallback to configured embedding model or general model
        if settings.llm_embeddings_model_name:
            self._detected_embeddings_model = settings.llm_embeddings_model_name
            print(f"📋 Using configured embeddings model: {self._detected_embeddings_model}")
            return self._detected_embeddings_model
        self._detected_embeddings_model = self._detected_model or self.model
        print(f"📋 Using model for embeddings: {self._detected_embeddings_model}")
        return self._detected_embeddings_model
    
    def get_model_name(self) -> str:
        """Get the detected or configured model name (non-async version for printing)"""
        if self._detected_model:
            return self._detected_model
        return self.model
    
    def _init_local_model(self):
        """Initialize local GGUF model (lazy loading)"""
        if self._local_llm is not None:
            return
        
        try:
            from llama_cpp import Llama
            
            if not os.path.exists(self.model_path):
                print(f"⚠️  Model not found: {self.model_path}")
                return
            
            print(f"🔧 Loading local GGUF model: {self.model_path}")
            # Use setting to control whether the local model exposes embedding() API
            enable_embedding = getattr(settings, 'llm_local_embeddings', True)
            self._local_llm = Llama(
                model_path=self.model_path,
                n_ctx=settings.llm_context_size,
                n_gpu_layers=settings.llm_gpu_layers,
                n_threads=settings.llm_threads,
                verbose=False
                , embedding=enable_embedding
            )
            self._local_llm_embedding_enabled = enable_embedding
            print(f"✅ Local model loaded")
        except ImportError:
            print("⚠️  llama-cpp-python not installed. Install with: pip install llama-cpp-python")
        except Exception as e:
            print(f"⚠️  Failed to load local model: {e}")

    def _parse_context_size_from_error(self, err_msg: str) -> Optional[int]:
        """
        Parse server error messages to extract numeric context size hints (n_ctx or n_ctx_slot).
        Returns numeric int context size if found, otherwise None.
        """
        if not err_msg:
            return None
        try:
            m = re.search(r"n_ctx_slot\s*[=:\s]\s*(\d+)", err_msg)
            if m:
                return int(m.group(1))
            m2 = re.search(r"context\s*(?:size|window)\s*:?\s*(\d+)", err_msg)
            if m2:
                return int(m2.group(1))
            m3 = re.search(r"task\.n_tokens\s*[=]\s*(\d+)", err_msg)
            if m3:
                return int(m3.group(1))
        except Exception:
            return None
        return None
    
    async def generate(self,
                      prompt: str,
                      max_tokens: Optional[int] = None,
                      temperature: float = None,
                      system_prompt: Optional[str] = None,
                      tools: Optional[List[Dict]] = None) -> str:
        """
        Generate completion using API server or local model.
        Automatically falls back to local if API fails.
        """
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens

        # Try API server first if not forced to use local
        api_exc = None
        if not self._use_local or self.force_remote_api:
            try:
                return await self._generate_api(prompt, max_tokens, temperature, system_prompt, tools)
            except Exception as e:
                api_exc = e
                print(f"⚠️  API failed: {e}")
                # If we are forcing the remote API, do not fall back to local model
                if self.force_remote_api:
                    raise
                print(f"   Attempting fallback to local model...")

        # Try local model fallback (only if API failed or local use requested)
        try:
            return await self._generate_local(prompt, max_tokens, temperature, system_prompt)
        except Exception as local_exc:
            print(f"⚠️  Local model failed: {local_exc}")
            # If there was also an API failure, raise a combined error for easier debugging
            if api_exc:
                raise RuntimeError(f"API error: {api_exc}; Local error: {local_exc}")
            # Otherwise, re-raise the local exception
            raise

    async def get_embeddings(self, texts: list[str] | str):
        """Return embeddings for a list of texts or single text using API or local model.

        Returns: List[List[float]] if input is list, else List[float] for single string.
        """
        if isinstance(texts, str):
            inputs = [texts]
        else:
            inputs = texts

        # Try using API
        try:
            # Determine the model for embeddings explicitly
            # 1) prefer detected embeddings model, 2) configured embedding model, 3) detected model for api_base, 4) fallback config
            model_for_embeddings = None
            if self._detected_embeddings_model:
                model_for_embeddings = self._detected_embeddings_model
            else:
                # try to detect embeddings model from embeddings base
                try:
                    model_for_embeddings = await self.detect_embeddings_model()
                except Exception:
                    model_for_embeddings = settings.llm_embeddings_model_name or self._detected_model or self.model

            payload = {"model": model_for_embeddings, "input": inputs}
            # Use dedicated embeddings base if available
            resp = await self.client.post(f"{self.embeddings_base}/v1/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Data likely has structure {'data': [{'embedding': [...]}, ...]}
            if isinstance(data, dict) and "data" in data:
                embeddings = [d.get("embedding") for d in data["data"]]
                return embeddings
        except httpx.HTTPStatusError as http_ex:
            try:
                body_str = http_ex.response.text
            except Exception:
                body_str = "<no response body>"
            server_message = None
            try:
                body_json = http_ex.response.json()
                if isinstance(body_json, dict):
                    server_message = body_json.get('message') or body_json.get('error')
            except Exception:
                body_json = None
            # Try to parse n_ctx from the message if available
            n_ctx = None
            if server_message:
                n_ctx = self._parse_context_size_from_error(server_message)
            print(f"⚠️  Embeddings API failed: {http_ex} (status={http_ex.response.status_code}): {body_str}")
            # Save any detected context size for adaptive chunking
            if n_ctx and not self._detected_server_context_size:
                self._detected_server_context_size = n_ctx
                print(f"🔎 Detected server context size via embeddings API error: {n_ctx}")
            # If fallback is disabled, raise structured error for upstream re-chunking logic
            if not getattr(settings, 'llm_embeddings_local_fallback_enabled', False):
                raise EmbeddingsAPIError("Embeddings API failed", status_code=http_ex.response.status_code, body=body_json or body_str, server_message=server_message, n_ctx=n_ctx)
        except Exception as e:
            # Generic exception - try to parse context size if possible and raise a structured error
            server_message = None
            n_ctx = None
            try:
                server_message = str(e)
                n_ctx = self._parse_context_size_from_error(server_message)
                if n_ctx and not self._detected_server_context_size:
                    self._detected_server_context_size = n_ctx
            except Exception:
                pass
            print(f"⚠️  Embeddings API failed: {e}")
            if not getattr(settings, 'llm_embeddings_local_fallback_enabled', False):
                raise EmbeddingsAPIError("Embeddings API failed", status_code=None, body=None, server_message=server_message, n_ctx=n_ctx)

        # Fallback to local model embeddings; llama-cpp-python may not expose embeddings method
        if not getattr(settings, 'llm_embeddings_local_fallback_enabled', False):
            raise RuntimeError("Embeddings API failed and local fallback for embeddings is disabled")
        try:
            # if we haven't initialized the local model yet, load it
            self._init_local_model()
            # Ensure local model is embedding-enabled when we want to call embed()
            if not self._local_llm_embedding_enabled:
                # try re-initializing with embeddings enabled
                print("🔧 Reinitializing local model with embedding support")
                try:
                    # Force recreate with embedding enabled
                    # Destroy previous instance reference first
                    self._local_llm = None
                    # Call init to create with the setting in config
                    self._init_local_model()
                except Exception:
                    pass
            if self._local_llm is not None:
                # llama-cpp-python may expose an embeddings API in newer versions as embed()
                if hasattr(self._local_llm, "embed"):
                    res = self._local_llm.embed(inputs)
                    # Expect res to be list of embeddings
                    return res
        except Exception as e:
            print(f"⚠️  Local embedding failed: {e}")

        raise RuntimeError("No embeddings method available (API or local model)")

    async def get_embeddings_for_documents(self, texts: list[str], chunk_size: Optional[int] = None, batch_size: int | None = None, min_batch: int = 1, delay: float = 0.15, max_retries: int = 3, chars_per_token: Optional[int] = None, max_chunk_tokens: Optional[int] = None):
        """
        Obtain a single embedding vector per document, even when documents are longer than `chunk_size`.
        Strategy:
          - Split each document into chunks up to `chunk_size` characters
          - Call get_embeddings() for all chunks in adaptive batches to avoid server 500s
          - Average embeddings for all chunks belonging to a document to obtain a final vector
        Returns: list[embedding] aligned to input `texts` (None where embedding failed)
        """
        if not texts:
            return []

        # Determine chunk_size in characters from token-based context detection if needed
        if chars_per_token is None:
            chars_per_token = getattr(settings, 'llm_chars_per_token', 4)
        detected_n_ctx = max_chunk_tokens or self._detected_server_context_size or getattr(settings, 'llm_context_size', None)
        if detected_n_ctx is None:
            detected_n_ctx = 4096
        if chunk_size is None:
            # Use a configurable fraction of the embeddings model context for chunking
            ratio = getattr(settings, 'llm_chunk_context_ratio', 0.5)
            tokens_per_chunk = max(64, int(math.floor(detected_n_ctx * float(ratio))))
            char_chunk_size = int(tokens_per_chunk * chars_per_token)
            # Cap by the configured embeddings default chunk size to avoid excessively large requests
            default_char_chunk = getattr(settings, 'llm_embeddings_chunk_size_default', 4096)
            chunk_size = min(default_char_chunk, char_chunk_size)
            print(f"🔧 Computed chunk_size: {chunk_size} chars (tokens_per_chunk={tokens_per_chunk}, detected_n_ctx={detected_n_ctx}, chars_per_token={chars_per_token}, ratio={ratio})")

        # Build chunks per document
        docs_chunks = []  # list of lists
        chunk_to_doc_index = []  # flattened mapping index->doc_idx
        all_chunks = []
        for doc_idx, text in enumerate(texts):
            if text is None:
                docs_chunks.append([])
                continue
            if len(text) <= chunk_size:
                docs_chunks.append([text])
                all_chunks.append(text)
                chunk_to_doc_index.append(doc_idx)
            else:
                # split by whitespace preserving words across chunks to avoid cutting words (basic approach)
                chunks = []
                start = 0
                while start < len(text):
                    end = min(start + chunk_size, len(text))
                    # try to break on last whitespace if possible (avoid tokenization here)
                    if end < len(text):
                        wh = text.rfind(' ', start, end)
                        if wh > start:
                            end = wh
                    chunk = text[start:end]
                    chunks.append(chunk)
                    all_chunks.append(chunk)
                    chunk_to_doc_index.append(doc_idx)
                    start = end
                docs_chunks.append(chunks)

        # Resolve batch_size default from settings if None
        if batch_size is None:
            batch_size = getattr(settings, 'llm_embeddings_default_batch_size', 4)

        # Function to embed in batches with graceful shrinking on failure
        async def _split_text_into_smaller_chunks(text, target_size):
            # Splits `text` into chunks <= target_size by splitting on whitespace around midpoint.
            if len(text) <= target_size:
                return [text]
            # naive splitting by whitespace, try to preserve words
            mid = len(text) // 2
            left_break = text.rfind(' ', 0, mid)
            right_break = text.find(' ', mid, len(text))
            if left_break == -1 and right_break == -1:
                # no whitespace found; just split at mid
                left = text[:mid]
                right = text[mid:]
            else:
                # prefer nearest break
                if left_break == -1:
                    split_at = right_break
                elif right_break == -1:
                    split_at = left_break
                else:
                    # pick the break closer to mid
                    split_at = left_break if (mid - left_break) <= (right_break - mid) else right_break
                left = text[:split_at]
                right = text[split_at:].lstrip()
            res_left = await _split_text_into_smaller_chunks(left, target_size)
            res_right = await _split_text_into_smaller_chunks(right, target_size)
            return res_left + res_right

        # Use class-level context parser

        async def _embed_all_chunks(chunk_list, initial_batch=batch_size, min_batch=min_batch, delay_time=delay, max_retries_local=max_retries):
            n = len(chunk_list)
            results = [None] * n
            i = 0
            cur_batch = initial_batch
            while i < n:
                if cur_batch <= 0:
                    cur_batch = 1
                end = min(i + cur_batch, n)
                batch = chunk_list[i:end]
                try:
                    # call underlying get_embeddings which returns list of embeddings aligned with input
                    # Debug: show attempt
                    # print(f"🔍 Embedding batch size {len(batch)} (starting idx {i})")
                    embs = await self.get_embeddings(batch)
                    if not embs:
                        # treat as failure to trigger shrinking
                        raise RuntimeError("Empty embeddings returned")
                    for j, emb in enumerate(embs):
                        results[i + j] = emb
                    i = end
                    await asyncio.sleep(delay_time)
                except Exception as e:
                    err_txt = str(e).lower()
                    # Attempt to parse server context size and record it to adaptively backoff
                    detected_ctx = None
                    if isinstance(e, EmbeddingsAPIError) and getattr(e, 'n_ctx', None):
                        detected_ctx = e.n_ctx
                    else:
                        detected_ctx = self._parse_context_size_from_error(str(e))
                    if detected_ctx and not self._detected_server_context_size:
                        self._detected_server_context_size = detected_ctx
                        print(f"🔎 Detected server context size: {detected_ctx}")
                    # If the server returned a structured error saying the request is too large and provided n_ctx, resplit using tokens-based chunking
                    if isinstance(e, EmbeddingsAPIError) and getattr(e, 'n_ctx', None):
                        n_ctx = e.n_ctx
                        # Only proceed if the server-reported context is smaller than our current chunking
                        # Convert current chunk_size (chars) back to token-estimate to compare
                        cur_token_estimate = max(1, int(chunk_size / max(1, chars_per_token)))
                        if n_ctx < cur_token_estimate:
                            print(f"🔁 Rebuilding chunks: server context {n_ctx} smaller than current chunk token estimate {cur_token_estimate}")
                            # compute new chunk_size based on n_ctx
                            new_tokens_per_chunk = max(64, int(math.floor(n_ctx * 0.8)))
                            new_chunk_chars = int(new_tokens_per_chunk * chars_per_token)
                            # Re-run with new chunk size
                            return await self.get_embeddings_for_documents(texts, chunk_size=new_chunk_chars, batch_size=initial_batch, min_batch=min_batch, delay=delay_time, max_retries=max_retries_local, chars_per_token=chars_per_token, max_chunk_tokens=n_ctx)
                    # If server returned a size-related error, try to re-chunk the offending content into smaller text chunks
                    if 'too large' in err_txt or 'increase the physical batch size' in err_txt or 'exceeds the available context size' in err_txt:
                        print(f"⚠️  Embedding server indicates request too large: {e}. Attempting to split chunks further.")
                        # Re-chunk the current batch: replace each chunk with multiple smaller ones and try them individually
                        # Use configured backoff sequence if adaptive backoff is enabled
                        backoff_seq = getattr(settings, 'llm_embeddings_chunk_backoff_sequence', [4096, 2048, 1024, 512, 256, 128])
                        backoff_seq = sorted(list(dict.fromkeys(backoff_seq)), reverse=True)
                        # Ensure monotonic decreasing order and filter sizes smaller than current chunk_size
                        cur_chunk_size = chunk_size
                        # If server context size known, use that to cap backoff sizes
                        if self._detected_server_context_size and getattr(settings, 'llm_embeddings_adaptive_backoff_enabled', True):
                            # heuristically convert tokens to approximate chars using factor 4
                            approx_chars = max(128, int(self._detected_server_context_size * 4))
                            backoff_seq = [s for s in backoff_seq if s <= approx_chars]
                            if not backoff_seq:
                                backoff_seq = [max(128, approx_chars // 4)]

                        for j_local, original_chunk in enumerate(batch):
                            if not original_chunk:
                                continue
                            doc_idx_local = i + j_local
                            # attempt to split this chunk into smaller character-based subchunks using backoff sequence
                            smaller_chunks = None
                            for target_size in backoff_seq:
                                if target_size >= len(original_chunk):
                                    # no-op, chunk is small enough
                                    continue
                                try:
                                    smaller = await _split_text_into_smaller_chunks(original_chunk, target_size)
                                    if len(smaller) > 1:
                                        smaller_chunks = smaller
                                        break
                                except Exception:
                                    continue
                            if smaller_chunks is None:
                                # fall back to simple halving if we couldn't find a split in the sequence
                                try:
                                    smaller_chunks = await _split_text_into_smaller_chunks(original_chunk, max(128, len(original_chunk) // 2))
                                except Exception:
                                    smaller_chunks = [original_chunk]
                            if len(smaller_chunks) == 1:
                                # couldn't split, we'll let normal per-item retry handle
                                continue
                            # Try to embed these smaller chunks
                            # Note: we'll call get_embeddings directly with smaller chunks
                            try:
                                sub_embs = await self.get_embeddings(smaller_chunks)
                                # average back to a single vector
                                if sub_embs and len(sub_embs) > 0:
                                    vec_len = len(sub_embs[0])
                                    sum_vec = [0.0]*vec_len
                                    for sv in sub_embs:
                                        if not sv:
                                            continue
                                        for vi in range(len(sv)):
                                            sum_vec[vi] += sv[vi]
                                    avg_vec = [x/len(sub_embs) for x in sum_vec]
                                    # assign back
                                    results[doc_idx_local] = avg_vec
                                else:
                                    # fallthrough to shrinking behavior below
                                    pass
                            except Exception as esub:
                                # If the re-chunk attempt fails, we'll fall back to shrinking batch size
                                print(f"⚠️  Subchunk embedding failed: {esub}")
                                pass
                        # Continue loop but shrink batch if necessary
                    # shrink batch if possible
                    if cur_batch > min_batch:
                        old_batch = cur_batch
                        cur_batch = max(min_batch, cur_batch // 2)
                        # double wait to be polite when we hit errors
                        await asyncio.sleep(delay_time * 2)
                        continue
                    # min-batch failing - try per item with retries
                    for j in range(i, end):
                        tries = 0
                        while tries < max_retries_local:
                            try:
                                em = await self.get_embeddings([chunk_list[j]])
                                results[j] = (em[0] if isinstance(em, list) and len(em) > 0 else None)
                                break
                            except Exception as e2:
                                tries += 1
                                await asyncio.sleep(delay_time * (tries + 1))
                        if tries >= max_retries_local and results[j] is None:
                            # give up this chunk
                            results[j] = None
                    i = end
            return results

        # Embed all chunks
        chunk_embeddings = await _embed_all_chunks(all_chunks, initial_batch=batch_size, min_batch=min_batch, delay_time=delay, max_retries_local=max_retries)

        # Now aggregate per document by averaging
        doc_embeddings = []
        # build list of lists per doc
        per_doc_embs = [[] for _ in range(len(texts))]
        for idx, emb in enumerate(chunk_embeddings):
            doc_idx = chunk_to_doc_index[idx]
            if emb is not None:
                per_doc_embs[doc_idx].append(emb)

        for doc_chunks_emb in per_doc_embs:
            if not doc_chunks_emb:
                doc_embeddings.append(None)
            else:
                # average the vectors elementwise
                length = len(doc_chunks_emb)
                # handle variable-length vectors unlikely but guard
                vec_len = len(doc_chunks_emb[0])
                sum_vec = [0.0] * vec_len
                for v in doc_chunks_emb:
                    if not v:
                        continue
                    for i in range(vec_len):
                        sum_vec[i] += v[i]
                avg_vec = [x / length for x in sum_vec]
                doc_embeddings.append(avg_vec)

        return doc_embeddings
    
    async def _generate_api(self,
                           prompt: str,
                           max_tokens: int,
                           temperature: float,
                           system_prompt: Optional[str],
                           tools: Optional[List[Dict]] = None) -> str:
        """Generate using API server (llama.cpp, LM Studio, etc.)"""

        # Detect model if not already done
        if not self._model_detection_attempted:
            await self.detect_model()

        # Use chat template to format the conversation
        messages = [{"role": "user", "content": prompt}]
        formatted_input = self.chat_template.format_messages(messages, system_prompt=system_prompt, tools=tools)

        # Determine API endpoint and payload format based on chat template
        # For templates that generate raw prompts (not OpenAI-style messages), use /completions endpoint
        if self.chat_template_name in ["qwen3", "qwen3-thinking", "gemma", "gemma2", "gemma3", "llama", "llama2", "llama3", "mistral", "phi3", "chatml"]:
            # For these templates, use the formatted input as a single prompt
            payload = {
                "model": self._detected_model or self.model,
                "prompt": formatted_input,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": settings.llm_top_p
            }
            # Use the basic /completions endpoint for raw prompt inputs
            api_endpoint = f"{self.api_base}/completions"
        else:
            # For standard OpenAI format (or when template is unknown/default), use messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self._detected_model or self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": settings.llm_top_p
            }
            # Use the standard /chat/completions endpoint for message-based inputs
            api_endpoint = f"{self.api_base}/chat/completions"

        # If stop tokens are configured, include them in the API payload
        if getattr(settings, 'llm_stop_tokens', None):
            payload["stop"] = settings.llm_stop_tokens

        model_display = self._detected_model or self.model
        print(f"🔍 Sending to LLM API:")
        print(f"   URL: {api_endpoint}")
        print(f"   Model: {model_display} (detected: {self._detected_model is not None})")
        print(f"   Template: {self.chat_template_name}")
        print(f"   Endpoint: {api_endpoint.split('/')[-1]}")
        if "messages" in payload:
            print(f"   Messages: {len(payload['messages'])} messages")
        else:
            print(f"   Prompt length: {len(payload['prompt'])} chars")
        print(f"   Payload: {payload}")

        try:
            response = await self.client.post(
            api_endpoint,
            json=payload
        )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            # Detect llama.cpp style context error and raise a specialized exception
            # The server returns a 400 with a message like: "the request exceeds the available context size, try increasing it"
            txt = http_err.response.text or ""
            try:
                j = http_err.response.json()
                if isinstance(j, dict) and j.get("error"):
                    txt = j.get("error")
            except Exception:
                pass
            # Try to parse numbers like 'n_ctx_slot = 8192' and 'task.n_tokens = 10225'
            n_ctx = None
            m_ctx = re.search(r"n_ctx_slot\s*=\s*(\d+)", txt)
            if m_ctx:
                n_ctx = int(m_ctx.group(1))
                self._detected_server_context_size = n_ctx
            if "exceeds the available context size" in txt.lower() or "request exceeds the available context size" in txt.lower():
                raise ContextSizeExceededError(f"Context too large trying to use model; details: {txt}", n_ctx=n_ctx, server_message=txt)
            # If no special handling, re-raise
            raise

        try:
            result = response.json()
            print(f"🔍 API Response: {result}")

            # Handle OpenAI format (gpt models)
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                    if content:
                        return content

            # If we get here, response was malformed
            print(f"⚠️  Unexpected response format: {result}")
            return ""
        except (KeyError, ValueError) as e:
            print(f"❌ Failed to parse API response: {e}")
            print(f"   Raw response: {response.text}")
            return ""


    async def _generate_local(self,
                             prompt: str,
                             max_tokens: int,
                             temperature: float,
                             system_prompt: Optional[str],
                             tools: Optional[List[Dict]] = None) -> str:
        """Generate using local GGUF model"""
        self._init_local_model()

        if self._local_llm is None:
            raise RuntimeError("Neither API nor local model available")

        # Use chat template to format the conversation for local generation
        messages = [{"role": "user", "content": prompt}]
        if self.chat_template_name in ["qwen3"]:
            # For Qwen3 template with local model, format as a single prompt
            full_prompt = self.chat_template.format_messages(messages, system_prompt=system_prompt, tools=tools)
        else:
            # Standard format for local model
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

        # Generate (synchronous call, but we're in async context)
        # Note: llama-cpp-python is sync, so we just call it directly
        # In production, might want to use asyncio.to_thread()
        output = self._local_llm(
            full_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=settings.llm_top_p,
            stop=getattr(settings, 'llm_stop_tokens', None),
            echo=False
        )

        return output["choices"][0]["text"].strip()


    async def stream_generate(self,
                             prompt: str,
                             max_tokens: Optional[int] = None,
                             temperature: float = None,
                             system_prompt: Optional[str] = None,
                             tools: Optional[List[Dict]] = None):
        """Stream generation token-by-token using API server."""
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens

        if not self._model_detection_attempted:
            await self.detect_model()

        # Use chat template to format the conversation for streaming
        messages = [{"role": "user", "content": prompt}]
        formatted_input = self.chat_template.format_messages(messages, system_prompt=system_prompt, tools=tools)

        # Determine API endpoint and payload format based on chat template
        # For templates that generate raw prompts (not OpenAI-style messages), use /completions endpoint
        if self.chat_template_name in ["qwen3", "qwen3-thinking", "gemma", "gemma2", "gemma3", "llama", "llama2", "llama3", "mistral", "phi3", "chatml"]:
            # For these templates, use the formatted input as a single prompt
            payload = {
                "model": self._detected_model or self.model,
                "prompt": formatted_input,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": settings.llm_top_p,
                "stream": True
            }
            # Use the basic /completions endpoint for raw prompt inputs
            api_endpoint = f"{self.api_base}/completions"
        else:
            # For standard OpenAI format (or when template is unknown/default), use messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self._detected_model or self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": settings.llm_top_p,
                "stream": True
            }
            # Use the standard /chat/completions endpoint for message-based inputs
            api_endpoint = f"{self.api_base}/chat/completions"

        if getattr(settings, 'llm_stop_tokens', None):
            payload["stop"] = settings.llm_stop_tokens

        print(f"🔍 Streaming from LLM API...")
        print(f"   Template: {self.chat_template_name}")
        print(f"   Endpoint: {api_endpoint.split('/')[-1]}")
        if "messages" in payload:
            print(f"   Messages: {len(payload['messages'])} messages")
        else:
            print(f"   Prompt length: {len(payload['prompt'])} chars")

        async with self.client.stream(
            "POST",
            api_endpoint,
            json=payload
        ) as response:
            # If the server returns an error status, attempt to read the body
            try:
                response.raise_for_status()
            except Exception as e:
                # Guarded reading of the error body to preserve debug visibility
                try:
                    text = await response.aread()
                    logger.error(f"LLM server error {response.status_code}: {text}")
                except Exception:
                    logger.error(f"LLM server returned {response.status_code} without readable body")
                raise

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get("choices"):
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue


    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


class ContextSizeExceededError(Exception):
    def __init__(self, message: str, n_ctx: Optional[int] = None, server_message: Optional[str] = None):
        super().__init__(message)
        self.n_ctx = n_ctx
        self.server_message = server_message
