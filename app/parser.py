"""
parser.py — Pure text extraction functions.

These functions take a raw HN comment string and extract structured fields.
They have no side effects: no I/O, no DB, no network.  That makes them
trivial to test and trivial to swap out later.

Design notes
────────────
• Every function has a defined fallback (never raises, never returns None).
• `classify_remote` uses priority ordering: more specific patterns win over
  more general ones.  The order matters — "us-only" must be checked before
  "global" because "global" is the catch-all.
• `extract_tech_tags` uses an explicit allowlist.  This avoids false positives
  from natural-language words that look like tech (e.g. "Go" in "Go ahead").
  The list is deliberately small to start; add to it as real data demands.
"""

import re

# ── Company & role ────────────────────────────────────────────────────────────


def extract_company(text: str) -> str:
    """Return the first pipe-separated segment, stripped.

    HN 'Who's Hiring' posters conventionally format their comment as:
        Company | Role | Location/Remote | ...
    We rely on this convention as the primary extraction signal.
    """
    if "|" not in text:
        return "Unknown"
    parts = text.split("|")
    company = parts[0].strip()
    return company if company else "Unknown"


def extract_role(text: str) -> str:
    """Return the second pipe-separated segment, stripped.

    Returns "Unknown" if there are fewer than three pipe segments.
    (Company | Role | Location).
    """
    parts = text.split("|")
    if len(parts) < 3:
        return "Unknown"
    role = parts[1].strip()
    return role if role else "Unknown"


# ── Remote classification ─────────────────────────────────────────────────────

# Each entry is (pattern, category).  Patterns are evaluated in order; the
# first match wins.  More specific patterns must come before general ones.
_REMOTE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Explicit negation or hybrid (catches "no remote info whatsoever")
    (
        re.compile(r"\b(no remote|not remote|onsite|hybrid)\b", re.I),
        "onsite",
    ),
    # US-only signals
    (
        re.compile(
            r"\b(us[- ]only|u\.?s\.?[- ]only|us[- ]based|usa\s+remote|united states only|usa\s*(and|or|/)\s*canada)\b",
            re.I,
        ),
        "us-only",
    ),
    # EU / EMEA signals
    (
        re.compile(
            r"\b(eu[- ]only|eu remote|europe[an]*\s+remote|emea|uk[- ]only|united kingdom|europe|\beu\b)\b",
            re.I,
        ),
        "eu-only",
    ),
    # Timezone-constrained remote
    (
        re.compile(r"\b(timezone overlap|tz overlap|cet|est overlap)\b", re.I),
        "tz-limited",
    ),
    # Regional restricted remote (forces onsite instead of global)
    (
        re.compile(
            r"\bremote\s*[\(\-\,:]\s*(india|uk|united kingdom|canada|latam|america|asia|australia)\b",
            re.I,
        ),
        "onsite",
    ),
    # Truly global remote — checked after regional signals
    (
        re.compile(
            r"\b(worldwide|global remote|remote.{0,20}anywhere|fully remote)\b", re.I
        ),
        "global",
    ),
    # Plain "remote" with no qualifier → treat as global
    (re.compile(r"\bremote\b", re.I), "global"),
]


def classify_remote(text: str) -> str:
    """Classify the remote policy described in *text*.

    Returns one of: "global" | "us-only" | "eu-only" | "tz-limited" | "onsite"
    """
    for pattern, category in _REMOTE_PATTERNS:
        if pattern.search(text):
            return category
    return "onsite"


# ── Tech tag extraction ───────────────────────────────────────────────────────

# Canonical display name → list of patterns that identify it.
# Patterns are matched case-insensitively against the full comment text.
_TECH_ALLOWLIST: dict[str, list[str]] = {
    "Python": [r"\bpython\b"],
    "Go": [r"\bgolang\b", r"\bgo\b(?!\s+ahead)"],  # avoid "go ahead"
    "Rust": [r"\brust\b"],
    "TypeScript": [r"\btypescript\b", r"\bts\b"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b"],
    "React": [r"\breact\b(?!\.js)"],
    "Next.js": [r"\bnext\.?js\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Django": [r"\bdjango\b"],
    "Flask": [r"\bflask\b"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b", r"\bpg\b"],
    "SQLite": [r"\bsqlite\b"],
    "Redis": [r"\bredis\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Docker": [r"\bdocker\b"],
    "AWS": [r"\baws\b", r"\bamazon web services\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle cloud\b"],
    "Azure": [r"\bazure\b"],
    "gRPC": [r"\bgrpc\b"],
    "GraphQL": [r"\bgraphql\b"],
    "Kafka": [r"\bkafka\b"],
    "PyTorch": [r"\bpytorch\b"],
    "TensorFlow": [r"\btensorflow\b"],
    "CUDA": [r"\bcuda\b"],
    "Elixir": [r"\belixir\b"],
    "Haskell": [r"\bhaskell\b"],
    "Scala": [r"\bscala\b"],
    "Java": [r"\bjava\b(?!script)"],
    "C++": [r"\bc\+\+\b"],
    "Terraform": [r"\bterraform\b"],
}

# Pre-compile for speed.
_COMPILED_TECH: list[tuple[str, list[re.Pattern]]] = [
    (name, [re.compile(p, re.I) for p in patterns])
    for name, patterns in _TECH_ALLOWLIST.items()
]


def extract_tech_tags(text: str) -> list[str]:
    """Return a sorted list of recognised technology names found in *text*."""
    if not text:
        return []
    found = []
    for name, patterns in _COMPILED_TECH:
        if any(p.search(text) for p in patterns):
            found.append(name)
    return sorted(found)
