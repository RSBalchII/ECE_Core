import html
import json
import re

EMOJI_REGEX = re.compile(
    "[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]",
    flags=re.UNICODE,
)

JSON_LIKE_PATTERNS = [re.compile(p) for p in [r"\{\s*\".*\"\s*:\s*", r"\[\s*\{", r'"response_content"', r'"timestamp"']]
HTML_LIKE_PATTERNS = [re.compile(p) for p in [r'<\s*\/?\w+[^>]*>', r'<a\s+href=', r'<script\b', r'<div\b', r'<p\b']]

SPAM_KEYWORDS = ['erotik', 'click here', 'buy now', 'free', 'cheap', 'subscribe now']

TECHNICAL_KEYWORDS = ['error', 'exception', 'traceback', 'sudo', 'apt-get', 'npm', 'pip', 'docker', 'cargo', 'journal', 'systemd', 'kernel', 'trace', 'failed', 'stacktrace']


def is_json_like(text: str) -> bool:
    if not text:
        return False
    for p in JSON_LIKE_PATTERNS:
        if p.search(text):
            return True
    return False


def is_html_like(text: str) -> bool:
    if not text:
        return False
    for p in HTML_LIKE_PATTERNS:
        if p.search(text):
            return True
    return False


def remove_html_tags(text: str) -> str:
    return re.sub(r'<[^>]+>', ' ', text)


def strip_emojis(text: str) -> str:
    return EMOJI_REGEX.sub('', text)


def extract_text_from_json(content: str) -> str:
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            for k in ('response_content', 'content', 'text', 'message', 'response'):
                if k in obj and isinstance(obj[k], str):
                    return obj[k]
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


# ---------------------- Technical Normalization ----------------------
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\\\")
UNIX_PATH_RE = re.compile(r"/(?:[\w\-\.@]+/)+[\w\-\.@]+")
HEXDUMP_RE = re.compile(r"(?:0x[0-9a-fA-F]{2,}|[0-9A-Fa-f]{2,}(?:\s+[0-9A-Fa-f]{2,}){4,})")


def contains_ansi_codes(text: str) -> bool:
    return bool(ANSI_ESCAPE_RE.search(text))


def contains_windows_path(text: str) -> bool:
    m = re.search(r"[A-Za-z]:", text)
    if not m:
        return False
    idx = m.end()
    if idx < len(text) and text[idx] in ('\\', '/'):
        return True
    return False


def contains_unix_path(text: str) -> bool:
    if '/usr/' in text or '/bin/' in text or '/home/' in text:
        return True
    return bool(UNIX_PATH_RE.search(text))


def contains_hex_dump(text: str) -> bool:
    return bool(HEXDUMP_RE.search(text))


def normalize_technical_content(text: str) -> str:
    """Normalize technical content by removing/annotating noisy artifacts while preserving semantic metadata.
    The function detects ANSI/color codes, OS paths, and hex dumps and inserts human-readable annotations
    such as [Context: Terminal Output], [OS: Linux], [OS: Windows], and [Binary Data Omitted].
    """
    if not text:
        return ''
    tags = []
    t = str(text)
    # ANSI sequences
    if contains_ansi_codes(t):
        t = ANSI_ESCAPE_RE.sub(' ', t)
        tags.append('[Context: Terminal Output]')
    # Windows paths
    if contains_windows_path(t):
        tags.append('[OS: Windows]')
        t = WINDOWS_PATH_RE.sub(lambda m: (m.group(0)[:60] + '...' if len(m.group(0)) > 70 else m.group(0)), t)
    # Unix paths
    if contains_unix_path(t):
        tags.append('[OS: Linux]')
        t = UNIX_PATH_RE.sub(lambda m: (m.group(0)[:80] + '...' if len(m.group(0)) > 80 else m.group(0)), t)
    # Hex dump / binary-like sequences
    if contains_hex_dump(t):
        tags.append('[Binary Data Omitted]')
        t = HEXDUMP_RE.sub('[binary_data]', t)
    # If there are HTML-like artifacts but we want a log context, annotate with [Context: HTML]
    if is_html_like(t):
        tags.append('[Context: HTML]')
        t = remove_html_tags(t)
    # Strip control characters
    t = re.sub(r'\x00|\x07|\x0b|\x0c', ' ', t)
    t = re.sub(r'\s+', ' ', html.unescape(t)).strip()
    if tags:
        annotation = ' '.join(sorted(set(tags))) + ' '
        t = annotation + t
    return t

# ---------------------- End Technical Normalization ----------------------


def clean_content(text: str, remove_emojis: bool = True, remove_non_ascii: bool = False, annotate_technical: bool = False) -> str:
    if not text:
        return ''
    t = text.strip()
    # If requested, apply technical normalization which will remove/annotate ANSI codes, paths, and hex dumps
    if annotate_technical:
        t = normalize_technical_content(t)
    if t.startswith('{') or t.startswith('[') or '"response_content"' in t:
        t2 = extract_text_from_json(t)
        if isinstance(t2, str) and t2:
            t = t2
    t = remove_html_tags(t)
    t = html.unescape(t)
    if remove_emojis:
        t = strip_emojis(t)
    if remove_non_ascii:
        t = ''.join([c for c in t if ord(c) < 128])
    t = re.sub(r'[^\w\s\.,;:\-\'"@#%\(\)\?\/\\]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def has_technical_signal(text: str) -> bool:
    """Detect strings that indicate the text is technical/log-like and should be preserved.
    This will detect shell prompts, package managers, version numbers, file paths, and error markers.
    """
    if not text:
        return False
    t = text.lower()
    # Quick patterns
    if 'sudo' in t or 'apt-get' in t or 'npm ' in t or 'pip ' in t or 'docker ' in t or 'cargo ' in t:
        return True
    # Version numbers
    if re.search(r'v\d+\.\d+(?:\.\d+)?', text):
        return True
    # File paths
    if re.search(r'\/\w+\/\w+', text) or re.search(r'[A-Za-z]:\\\\', text):
        return True
        # Allow square brackets so annotation tokens like [Context: Terminal Output] are preserved
        t = re.sub(r'[^\w\s\.,;:\-\'"@#%\(\)\[\]\?/\\]+', ' ', t)
    for k in TECHNICAL_KEYWORDS:
        if k in t:
            return True
    # Shell-like prompts or stack traces
    if re.search(r'\b(error|exception|traceback|failed)\b', t):
        return True
    if re.search(r'\b[\$#] ', text):
        return True
    return False


def is_token_soup(text: str, *, min_tokens: int = 3) -> bool:
    """Detect whether a piece of text is likely corrupted/garbled (token soup).

    Heuristics used:
    - High fraction of tokens that contain code-like characters (parentheses, ';', '{', '}', '->', etc.)
    - High fraction of tokens that are hexadecimal strings or long digit-only sequences
    - High fraction of tokens that are one-letter (indicative of binary tokens or low-quality text)
    - Low fraction of alphabetic words (few dictionary-like words)
    - Large runs of punctuation or non-letter characters
    These heuristics are intentionally conservative — we prefer to flag likely garbage and
    leave marginal cases untouched.
    """
    if not text or not text.strip():
        return False
    s = text.strip()
    # Quick filters
    if len(s) < 40:
        # short content unlikely to be long corrupted token soup
        return False
    tokens = re.findall(r"\S+", s)
    if len(tokens) < min_tokens:
        return False
    total = len(tokens)
    code_like = 0
    hex_like = 0
    one_letter = 0
    no_vowel = 0
    alpha_like = 0
    long_token = 0
    for t in tokens:
        if len(t) == 1:
            one_letter += 1
        if re.search(r'[(){}\[\]<>;=:\\|/\\\\@#%\$]', t):
            code_like += 1
        if re.fullmatch(r'0x[0-9a-fA-F]{8,}', t) or re.fullmatch(r'[A-Fa-f0-9]{16,}', t):
            hex_like += 1
        if re.search(r'[0-9]', t) and re.search(r'[A-Za-z]', t) is None and len(t) >= 8:
            hex_like += 1
        if len(t) >= 6 and not re.search(r'[aeiouAEIOU]', t):
            no_vowel += 1
        if re.fullmatch(r'[A-Za-z]+', t):
            alpha_like += 1
        if len(t) > 30:
            long_token += 1
    # Ratios
    code_like_ratio = code_like / total
    hex_ratio = hex_like / total
    one_letter_ratio = one_letter / total
    no_vowel_ratio = no_vowel / total
    alpha_ratio = alpha_like / total
    long_token_ratio = long_token / total
    # If we see many code-like tokens or hex-like tokens, it's probably corrupted
    if code_like_ratio > 0.25 or hex_ratio > 0.05 or one_letter_ratio > 0.25:
        return True
    # If very few alphabetic words and many tokens are long & vowel-free, flag
    if alpha_ratio < 0.25 and (no_vowel_ratio > 0.2 or long_token_ratio > 0.05):
        return True
    # If we see run of excessive punctuation
    punct_runs = re.findall(r'[^\w\s]{6,}', s)
    if len(punct_runs) > 0:
        return True
    return False


def sanitize_token_soup(text: str) -> str:
    """Return a sanitized version of a token-soup string. We aim to preserve any readable text
    but remove or collapse obvious code fragments, long hex/ids, and JSON-like containers.
    This is a best-effort function — it can't recover content that has been transformed beyond
    recognition, but it will remove obvious artifacts so downstream summarizers see cleaner input.
    """
    if not text:
        return ''
    t = text
    # Remove fenced code blocks
    t = re.sub(r'```.*?```', ' ', t, flags=re.DOTALL)
    # Remove common code patterns: function calls with arguments, memory copies
    t = re.sub(r'\b[A-Za-z_][A-Za-z0-9_]*\([^\)]*\)', ' ', t)
    # Remove long hex sequences
    t = re.sub(r'0x[0-9a-fA-F]{6,}', ' ', t)
    t = re.sub(r'\b[A-Fa-f0-9]{16,}\b', ' ', t)
    # Remove JSON-like structural content when large
    if len(t) > 200 and (t.strip().startswith('{') or t.strip().startswith('[')):
        t = extract_text_from_json(t)
    # Collapse multiple punctuation and whitespace
    t = re.sub(r'[<>\|\\]{1,}', ' ', t)
    t = re.sub(r'[^\w\s\.,;:\-\'"\(\)]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    # Truncate to a sensible length - we don't want to produce overly long sanitized strings
    if len(t) > 500:
        t = t[:500] + '...'
    return t
