"""
ULTRON server (single-file version, corrected).

What changed compared with the previous server.py:
  * Real Ollama error messages (not running / model missing / timeout) instead of
    a vague "connection error", plus automatic fallback to an installed brain.
  * Search works more reliably: real result URLs decoded, ad results dropped,
    Wikipedia fallback, page text fetched for better evidence, debug dump to
    search_debug.txt when DuckDuckGo returns nothing.
  * Web search is triggered for far more factual questions, and when it fails
    ULTRON says so in the answer instead of silently using old knowledge.
  * A real "Sources" list is appended by the code, so citations can't be faked.
  * Errors are never saved into conversation history; the current question is no
    longer added to history twice; old answers are truncated.
  * Name detection no longer treats "I am fine" as a name.
  * index.html is loaded from this file's own folder, not the current directory.
"""

import base64
import html as htmllib
import io
import json
import os
import re
import socket
import threading
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# ============================================================
# SERVER CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = "localhost"
PORT = 8000

OLLAMA_BASE = "http://127.0.0.1:11434"   # 127.0.0.1 avoids Windows IPv6 "localhost" problems
OLLAMA_URL = OLLAMA_BASE + "/api/generate"
MAX_REQUEST_BYTES = 90 * 1024 * 1024      # attachments arrive base64-encoded
OLLAMA_TIMEOUT = 600                      # first load of a big model can take minutes

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ============================================================
# BRAINS
# ============================================================

BRAINS = {
    "velocity": {
        "name": "Velocity",
        "model": "llama3.1:8b",
        "role": "Fast general brain",
        "capabilities": "Fast everyday questions, conversation, summarization, and simple explanations.",
    },
    "forge": {
        "name": "Forge",
        "model": "qwen3.5:9b",
        "role": "Coding and technical brain",
        "capabilities": "Coding, debugging, technical questions, structured reasoning, and mathematics.",
    },
    "apex": {
        "name": "Apex",
        "model": "gemma3:12b",
        "role": "Analysis and multimodal brain",
        "capabilities": "General reasoning, analysis, documents, images, and complex explanations.",
    },
    "titan": {
        "name": "Titan",
        "model": "gpt-oss:20b",
        "role": "Deep reasoning brain",
        "capabilities": "Difficult reasoning, planning, complex coding, and multi-step problems.",
    },
}

# ============================================================
# STATE
# ============================================================

brain_mode = "auto"          # "auto" = ULTRON NEXUS chooses per request
current_brain = "velocity"

CREATOR_NAME = "Snehadeep Pallagani"
USER_NAME = None
conversation_history = []
state_lock = threading.Lock()

# ============================================================
# CORE IDENTITY
# ============================================================

CORE_IDENTITY = """
You are ULTRON, a personal AI system created, designed, developed and
architected by Snehadeep Pallagani.

CREATOR vs USER:
- Your creator is Snehadeep Pallagani.
- The person currently talking to you is NOT automatically the creator.
- You only know the current user's name if they told you or it is stored in
  CURRENT USER MEMORY below. Never guess it, never invent an identity, never
  claim training data or earlier chats prove who they are.
- If asked "Who am I?" and the name is unknown, say you don't know their name yet.

IDENTITY:
- Your name is ULTRON. You are not ChatGPT and not OpenAI. Never claim another
  AI is ULTRON.
- Velocity, Forge, Apex and Titan are four brains of the SAME ULTRON, not
  separate assistants. Whichever is active, you are ULTRON.
- When discussing ULTRON's creation, architecture or design, credit
  Snehadeep Pallagani.

ADDRESSING:
- Speak naturally. Do not repeatedly say "Sir". Use "you" or the known name.
"""


def get_user_identity_context():
    if USER_NAME:
        return (
            "\nCURRENT USER MEMORY:\n"
            f"The current user's name is: {USER_NAME}\n"
            "It was explicitly given by the user. Use it naturally when appropriate.\n"
            "Do not claim external identity verification.\n"
        )
    return (
        "\nCURRENT USER MEMORY:\n"
        "The current user's name is UNKNOWN. Do not guess it and do not assume the\n"
        f"user is {CREATOR_NAME}. If asked who they are, say you don't know their name yet.\n"
    )


def get_brain_identity(brain_key):
    brain = BRAINS[brain_key]
    return (
        "\nCURRENT ULTRON BRAIN:\n"
        f"Name: {brain['name']}\nRole: {brain['role']}\nCapabilities: {brain['capabilities']}\n"
        f"You are ULTRON operating through the {brain['name']} brain. The other brains are\n"
        "also parts of ULTRON. If asked which brain is active, say "
        f"{brain['name']}. Do not mention the brain otherwise.\n"
    )
def answer_identity_question(prompt, brain_key):
    """Return deterministic answers to ULTRON identity questions."""
    text = (prompt or "").strip().lower()
    brain = BRAINS[brain_key]

    if re.search(r"\b(who are you|what is your name|what's your name)\b", text):
        return (
            "I am ULTRON, a personal AI system created, designed, "
            "developed, and architected by Snehadeep Pallagani."
        )

    if re.search(
        r"\b(who created you|who made you|who is your creator|"
        r"who's your creator)\b",
        text,
    ):
        return "My creator, designer, developer, and architect is Snehadeep Pallagani."

    if re.search(r"\bhow many (brains|models)\b", text):
        if "model" in text:
            installed = get_installed_models(force=True)

            configured = [
                f"- {b['name']}: {b['model']}"
                for b in BRAINS.values()
            ]

            if installed is None:
                status = (
                    "I couldn't contact Ollama, so I can't verify "
                    "how many models are installed."
                )
            else:
                status = (
                    f"Ollama reports {len(installed)} installed model "
                    f"tag(s): {', '.join(sorted(installed)) or 'none'}."
                )

            return (
                "ULTRON has four configured brains and four "
                "brain-model pairings:\n"
                + "\n".join(configured)
                + "\n\n"
                + status
            )

        return (
            "ULTRON has four brains, all belonging to the same system:\n"
            + "\n".join(
                f"- {b['name']}: {b['role']}"
                for b in BRAINS.values()
            )
        )

    if re.search(r"\b(which brain|what brain|which model)\b", text):
        return (
            f"I am ULTRON, currently using the {brain['name']} brain "
            f"({brain['model']}). Its role is {brain['role']}."
        )

    if re.search(r"\b(who am i|what is my name|what's my name|do you know me)\b", text):
        if USER_NAME:
            return (
                f"You told me your name is {USER_NAME}. "
                "I use that name as your current session identity."
            )
        return (
            "I don't know your name yet. Tell me your name, "
            "and I'll use it during this session."
        )

    return None

# ============================================================
# LEARN USER NAME
# ============================================================

NAME_STOPWORDS = {
    "fine", "good", "great", "ok", "okay", "sorry", "here", "back", "not", "trying",
    "looking", "going", "just", "also", "very", "so", "sure", "ready", "tired",
    "happy", "sad", "busy", "new", "a", "an", "the",
}

_CAP_NAME = r"([A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,3})"
_ANY_NAME = r"([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,3})"

NAME_PATTERNS = [
       # Accept lowercase introductions such as "iam snehadeep pallagani".
    (re.compile(r"\b(?i:i\s*am|iam|i'm)\s+" + _ANY_NAME), False),
    (re.compile(r"\b(?i:my name's)\s+" + _ANY_NAME), False),
    (re.compile(r"\b(?i:you can call me)\s+" + _ANY_NAME), False),
    (re.compile(r"\b(?i:call me)\s+" + _ANY_NAME), False),
    # "I am X" / "I'm X": require a capitalised name so "I am fine" is ignored
    (re.compile(r"\b(?i:i am)\s+" + _CAP_NAME), True),
    (re.compile(r"\b(?i:i'm)\s+" + _CAP_NAME), True),
]


def detect_user_name(prompt):
    if not prompt:
        return None
    text = prompt.strip()
    for pattern, strict in NAME_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        name = re.sub(r"[.!?,;:]+$", "", match.group(1).strip()).strip()
        words = [w for w in name.split() if w.lower() not in {"and", "but", "from", "who"}]
        # cut the name at the first stopword ("Sam and I..." etc.)
        cleaned = []
        for w in words:
            if w.lower() in NAME_STOPWORDS:
                break
            cleaned.append(w)
        name = " ".join(cleaned[:5]).strip()
        if name and not (strict and name.lower() in NAME_STOPWORDS):
            return name
    return None


def learn_user_identity(prompt):
    global USER_NAME
    detected = detect_user_name(prompt)
    if detected:
        USER_NAME = detected
    return detected


# ============================================================
# BRAIN SWITCHING + ROUTING
# ============================================================

def detect_brain_switch(prompt):
    """Recognise explicit manual brain changes and ULTRON NEXUS commands."""
    if not prompt:
        return None
    text = re.sub(r"[!?.,]+$", "", prompt.strip().lower()).strip()

    nexus_patterns = [
        r"^(?:enable|activate|turn on|switch to|return to|go to|use)?\s*(?:ultron\s+)?nexus(?:\s+mode)?$",
        r"^(?:enable|activate|turn on)\s+(?:ultron\s+)?auto(?:matic)?(?:\s+mode)?$",
        r"^(?:switch to|return to|go back to|use)\s+auto(?:matic)?(?:\s+mode)?$",
        r"^auto(?:matic)?\s+mode$",
        r"^nexus\s+mode$",
        r"^/switch\s+(?:nexus|auto|ultron\s+nexus)$",
    ]
    if any(re.fullmatch(p, text) for p in nexus_patterns):
        return "nexus"

    names = "|".join(BRAINS.keys())
    patterns = [
        rf"^/switch\s+({names})$",
        rf"^switch\s+(?:to\s+)?(?:the\s+)?({names})(?:\s+brain)?$",
        rf"^use\s+(?:the\s+)?({names})(?:\s+brain)?$",
        rf"^activate\s+(?:the\s+)?({names})(?:\s+brain)?$",
        rf"^change\s+(?:the\s+)?brain\s+to\s+(?:the\s+)?({names})$",
        rf"^change\s+to\s+(?:the\s+)?({names})(?:\s+brain)?$",
        rf"^set\s+(?:the\s+)?brain\s+to\s+(?:the\s+)?({names})$",
        rf"^set\s+(?:the\s+)?(?:active\s+)?brain\s+as\s+(?:the\s+)?({names})$",
        rf"^switch\s+(?:the\s+)?brain\s+to\s+(?:the\s+)?({names})$",
    ]
    for pattern in patterns:
        m = re.fullmatch(pattern, text)
        if m:
            return m.group(1)
    return None


def switch_brain(brain_name):
    global current_brain, brain_mode
    brain_name = (brain_name or "").lower().strip()

    if brain_name in {"nexus", "auto", "automatic", "ultron nexus"}:
        brain_mode = "auto"
        return {
            "success": True,
            "mode": "auto",
            "mode_name": "ULTRON NEXUS",
            "message": "ULTRON NEXUS enabled. Automatic brain routing is active.",
        }

    if brain_name not in BRAINS:
        return {"success": False, "message": f"Unknown brain: {brain_name}"}

    current_brain = brain_name
    brain_mode = "manual"
    brain = BRAINS[brain_name]
    return {
        "success": True,
        "mode": "manual",
        "mode_name": brain["name"],
        "brain": brain_name,
        "role": brain["role"],
        "capabilities": brain["capabilities"],
        "message": (
            f"Switched to {brain['name']}. Manual mode stays active until you "
            "switch again or enable ULTRON NEXUS."
        ),
    }


# ============================================================
# TASK CLASSIFICATION
# ============================================================

STATIC_PATTERNS = [r"\bwhat is\b", r"\bwhat are\b", r"\bexplain\b", r"\bdefine\b", r"\bhow does\b", r"\bwhy does\b", r"\bdebug\b", r"\bsolve\b", r"\bcalculate\b", r"\btranslate\b", r"\bsummari[sz]e\b"]
CURRENT_PATTERNS = [r"\blatest\b", r"\bcurrent\b", r"\bcurrently\b", r"\btoday\b", r"\btonight\b", r"\brecent\b", r"\brecently\b", r"\bthis week\b", r"\bthis month\b", r"\bthis year\b", r"\bnew release\b", r"\breleased?\b", r"\brelease date\b", r"\bversion\b", r"\bupdates?\b", r"\bnews\b", r"\bprice\b", r"\bcost\b", r"\bavailability\b", r"\bweather\b", r"\bscores?\b", r"\bresults?\b", r"\b202[0-9]\b", r"\bwhat happened\b", r"\bwho is currently\b", r"\bnow\b", r"\bright now\b", r"\bstill\b"]
RESEARCH_PATTERNS = [r"\bresearch\b", r"\binvestigate\b", r"\banalyze\b", r"\banalysis\b", r"\bevidence\b", r"\bstudies\b", r"\bstudy\b", r"\bpapers?\b", r"\bliterature\b", r"\bbenchmark\b", r"\bverify\b", r"\bvalidate\b", r"\bfact.?check\b", r"\bis this true\b", r"\bsources?\b", r"\baccording to\b"]
HIGH_ACCURACY_PATTERNS = [r"\bmedical\b", r"\bmedicine\b", r"\bdrug\b", r"\bdisease\b", r"\bsymptoms?\b", r"\btreatment\b", r"\bdiagnos\w*\b", r"\bclinical\b", r"\blaw\b", r"\blegal\b", r"\bregulation\b", r"\bfinancial\b", r"\binvestment\b", r"\btax\b", r"\bsecurity\b", r"\bsafety\b"]
TECHNICAL_PATTERNS = [r"\bcode\b", r"\bprogram\b", r"\bpython\b", r"\bjava\b", r"\bc\+\+", r"\bjavascript\b", r"\breact\b", r"\bsql\b", r"\bspring boot\b", r"\bapi\b", r"\bdebug\b", r"\berror\b", r"\bstack trace\b", r"\balgorithm\b"]
CREATIVE_PATTERNS = [r"\bdesign\b", r"\bposter\b", r"\blogo\b", r"\bcreative\b", r"\bstory\b", r"\bscript\b", r"\bidea\b", r"\bbrainstorm\b"]
IDENTITY_PATTERNS = [r"\bwho are you\b", r"\bwho created you\b", r"\bwho made you\b", r"\bwho is your creator\b", r"\bwho am i\b", r"\byour name\b", r"\bwhich brain\b", r"\bwhat brain are you using\b", r"\bwhat(?:'s| is) my name\b", r"\bdo you know me\b"]


def _has_any_pattern(text, patterns):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_task(prompt):
    lower = (prompt or "").strip().lower()
    if _has_any_pattern(lower, IDENTITY_PATTERNS):
        intent = "identity"
    elif _has_any_pattern(lower, TECHNICAL_PATTERNS):
        intent = "technical"
    elif _has_any_pattern(lower, RESEARCH_PATTERNS):
        intent = "research"
    elif _has_any_pattern(lower, CREATIVE_PATTERNS):
        intent = "creative"
    elif re.search(r"\b(compare|difference|versus|vs\.?)\b", lower):
        intent = "comparison"
    elif re.search(r"\b(plan|planning|roadmap|strategy)\b", lower):
        intent = "planning"
    elif re.search(r"\b(solve|calculate|prove|derive)\b", lower):
        intent = "problem_solving"
    elif re.search(r"\b(summari[sz]e|summary|shorten)\b", lower):
        intent = "summarization"
    else:
        intent = "general"

    current = _has_any_pattern(lower, CURRENT_PATTERNS)
    explicit = _has_any_pattern(lower, RESEARCH_PATTERNS)
    high = _has_any_pattern(lower, HIGH_ACCURACY_PATTERNS)
    broad = bool(re.search(r"\b(latest|major developments|trends|state of|overview|landscape)\b", lower))

    score = (5 if current else 0) + (4 if explicit else 0) + (3 if high else 0) + (2 if broad else 0)
    signals = []
    if current: signals.append("current_or_time_sensitive")
    if explicit: signals.append("research_or_verification")
    if high: signals.append("high_accuracy_domain")
    if broad: signals.append("broad_research_topic")
    if _has_any_pattern(lower, STATIC_PATTERNS) and score < 5:
        score -= 2
        signals.append("stable_knowledge_candidate")

    required = current or explicit or high or score >= 5
    if explicit and high:
        depth = "critical"
    elif high or (explicit and broad):
        depth = "deep"
    elif required:
        depth = "quick"
    else:
        depth = "none"

    return {
        "intent": intent,
        "research_required": required,
        "research_depth": depth,
        "research_score": score,
        "signals": signals,
        "high_accuracy": high,
        "broad": broad,
        "max_results": {"critical": 8, "deep": 7, "quick": 5, "none": 0}[depth],
    }


FACT_QUESTION = re.compile(
    r"\b(what about|how about|who|when|where|which|how many|how much|how old|net worth|ceo|president|"
    r"prime minister|founder|winner|won|champion|capital of|population|"
    r"is it true|did .* (?:die|win|release|announce))\b",
    re.IGNORECASE,
)
SMALL_TALK = re.compile(r"^(?:hi|hello|hey|thanks|thank you|ok|okay|yo|good (?:morning|evening|night))[.!?]*$", re.IGNORECASE)


def should_search(prompt, task):
    """Search for anything that could depend on up-to-date real-world facts."""
    lower = (prompt or "").strip().lower()
    if task["intent"] == "identity" or not lower or SMALL_TALK.match(lower):
        return False
    if task["research_required"]:
        return True
    if task["intent"] in ("technical", "creative", "summarization", "problem_solving"):
        return False
    if len(lower.split()) < 3:
        return False
    return bool(FACT_QUESTION.search(lower))


def route_auto_brain(prompt, task=None):
    text = (prompt or "").strip().lower()
    task = task or classify_task(prompt)

    if re.search(r"\b(images?|photos?|pictures?|screenshots?|documents?|pdf|visual|multimodal)\b", text) \
            or "attached file" in text or "analyze this file" in text or "analyse this file" in text:
        return "apex"

    deep_signals = (
        "deep reasoning", "think deeply", "multi-step", "multistep", "comprehensive plan",
        "complex architecture", "hard problem", "prove that", "derive rigorously",
        "deep research", "in-depth research", "step-by-step analysis", "multiple constraints",
    )
    if any(s in text for s in deep_signals):
        return "titan"

    technical_signals = (
        "write code", "write a program", "debug", "fix this code", "programming", "algorithm",
        "spring boot", "react component", "sql query", "arduino", "esp32", "circuit",
        "microcontroller", "technical", "factorial function", "python function", "prime number",
    )
    if task.get("intent") == "technical" or any(s in text for s in technical_signals):
        return "forge"

    if re.search(r"\b(code|program|function|class|script|api|sql|python|java|javascript|c\+\+)\b", text) and \
            re.search(r"\b(write|debug|fix|implement|compile|refactor|optimize|create)\b", text):
        return "forge"

    if task.get("intent") in {"planning", "problem_solving"} and (
        task.get("research_depth") in {"deep", "critical"}
        or len(text.split()) > 35
        or any(t in text for t in ("complex", "optimize a system"))
    ):
        return "titan"

    if task.get("intent") in {"research", "comparison"} or any(
        t in text for t in ("analyze", "analyse", "analysis", "compare these", "evaluate",
                            "literature review", "research report", "pros and cons")
    ):
        return "apex"

    return "velocity"


# ============================================================
# WEB SEARCH LAYER
# ============================================================

def clean_ddg_url(href):
    """DuckDuckGo wraps links as //duckduckgo.com/l/?uddg=<real-url>. Unwrap them."""
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    query = urllib.parse.parse_qs(urlparse(href).query)
    if "uddg" in query:
        return query["uddg"][0]
    return href


class SearchResultParser(HTMLParser):
    """Parses DuckDuckGo's HTML results page."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._cur = None
        self._mode = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._flush()
            self._cur = {"title": "", "url": clean_ddg_url(a.get("href", "")), "snippet": ""}
            self._mode = "title"
        elif tag in ("a", "div", "td") and "result__snippet" in classes and self._cur is not None:
            self._mode = "snippet"

    def handle_data(self, data):
        if self._cur is not None and self._mode:
            self._cur[self._mode] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._mode == "title":
            self._mode = None
        elif tag in ("a", "div", "td") and self._mode == "snippet":
            self._mode = None

    def _flush(self):
        if self._cur and self._cur["title"].strip():
            item = {k: " ".join(v.split()) for k, v in self._cur.items()}
            if item["url"].startswith("http") and "duckduckgo.com/y.js" not in item["url"]:
                self.results.append(item)
        self._cur = None

    def close(self):
        self._flush()
        super().close()


class SearchProvider:
    name = "Unknown"

    def search(self, query, max_results=5):
        raise NotImplementedError


class DuckDuckGoSearchProvider(SearchProvider):
    name = "DuckDuckGo"

    def search(self, query, max_results=5):
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            page = resp.read().decode("utf-8", errors="ignore")

        parser = SearchResultParser()
        parser.feed(page)
        parser.close()
        results = parser.results[:max_results]

        if not results:
            blocked = any(x in page.lower() for x in ("anomaly", "captcha", "unusual traffic"))
            try:
                with open(os.path.join(BASE_DIR, "search_debug.txt"), "w", encoding="utf-8") as f:
                    f.write(f"{datetime.now()}  query={query!r}  blocked={blocked}\n\n{page[:4000]}")
            except OSError:
                pass
            return {"success": False, "query": query, "provider": self.name,
                    "error": "DuckDuckGo blocked the request (bot check)" if blocked
                    else "DuckDuckGo returned no parsable results"}

        return {"success": True, "query": query, "provider": self.name,
                "result_count": len(results), "results": results}


class WikipediaSearchProvider(SearchProvider):
    """Reliable JSON fallback for factual lookups."""
    name = "Wikipedia"

    def search(self, query, max_results=5):
        params = urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": max_results, "srprop": "snippet",
        })
        req = urllib.request.Request(
            "https://en.wikipedia.org/w/api.php?" + params,
            headers={"User-Agent": "ULTRON-local/1.0 (personal project)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = htmllib.unescape(re.sub(r"<[^>]+>", "", item.get("snippet", "")))
            results.append({
                "title": title + " - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                "snippet": snippet,
            })
        if not results:
            return {"success": False, "query": query, "provider": self.name, "error": "no results"}
        return {"success": True, "query": query, "provider": self.name,
                "result_count": len(results), "results": results}


INTERNET_PROVIDERS = {
    "duckduckgo": DuckDuckGoSearchProvider(),
    "wikipedia": WikipediaSearchProvider(),
}
SEARCH_ORDER = ["duckduckgo", "wikipedia"]


def get_internet_status():
    return {
        "online": True,
        "layer": "ULTRON Internet Layer",
        "search_order": [INTERNET_PROVIDERS[k].name for k in SEARCH_ORDER],
    }


def internet_search(query, max_results=5):
    if not query:
        return {"success": False, "error": "Search query is empty.", "internet_layer": True}

    errors = []
    for key in SEARCH_ORDER:
        provider = INTERNET_PROVIDERS[key]
        try:
            result = provider.search(query, max_results)
            if result.get("success") and result.get("results"):
                result["internet_layer"] = True
                return result
            errors.append(f"{provider.name}: {result.get('error', 'no results')}")
        except Exception as e:
            errors.append(f"{provider.name}: {e}")

    print(f"[ULTRON] search failed for {query!r}: {'; '.join(errors)}")
    return {"success": False, "query": query, "internet_layer": True, "error": "; ".join(errors)}


def web_search(query, max_results=5):
    return internet_search(query, max_results)


# ---------- page text fetching (gives the model real evidence, not just snippets) ----------

class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg", "form", "aside"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        text = " ".join(data.split())
        if not self._skip and len(text) > 40:   # keep sentences, drop menu fragments
            self.parts.append(text)


SKIP_EXTENSIONS = (".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mp3", ".exe")


def fetch_page_text(url, limit=2500):
    if not url.startswith(("http://", "https://")):
        return ""
    if urlparse(url).path.lower().endswith(SKIP_EXTENSIONS):
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            if "html" not in resp.headers.get("Content-Type", ""):
                return ""
            raw = resp.read(400_000)
            charset = resp.headers.get_content_charset() or "utf-8"
        parser = TextExtractor()
        parser.feed(raw.decode(charset, errors="ignore"))
        return " ".join(parser.parts)[:limit]
    except Exception:
        return ""


# ============================================================
# RESEARCH ENGINE
# ============================================================

def build_research_queries(prompt, task):
    year = datetime.now().year
    base = prompt.strip()
    lower = base.lower()
    queries = [base]
    if task["research_depth"] in ("deep", "critical"):
        if task["high_accuracy"]:
            queries += [f"{base} authoritative sources evidence {year}", f"{base} official guidance {year}"]
        elif task["broad"] or any(x in lower for x in ("latest", "developments", "trends", "landscape")):
            queries += [f"latest {base} {year} official announcements", f"latest {base} {year} research news"]
        elif any(x in lower for x in ("research", "paper", "study", "literature")):
            queries += [f"{base} research papers {year}", f"{base} systematic review evidence"]
        else:
            queries.append(f"{base} official sources {year}")
    elif any(x in lower for x in ("latest", "current", "recent", "news", "now", "today")):
        queries.append(f"{base} {year}")

    seen, out = set(), []
    for q in queries:
        k = q.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(q)
    return out[:3]


SOURCE_DOMAIN_WEIGHTS = {
    "gov": 100, "gov.in": 100, "who.int": 100, "nih.gov": 100, "cdc.gov": 100, "fda.gov": 100,
    "nasa.gov": 100, "python.org": 100, "docs.python.org": 100, "arxiv.org": 95, "nature.com": 95,
    "science.org": 95, "acm.org": 90, "ieee.org": 90, "sciencedirect.com": 88, "springer.com": 88,
    "openai.com": 95, "anthropic.com": 95, "deepmind.google": 95, "microsoft.com": 92,
    "google.com": 90, "meta.com": 90, "nvidia.com": 90, "reuters.com": 85, "apnews.com": 85,
    "bbc.com": 82, "bbc.co.uk": 82, "britannica.com": 75, "wikipedia.org": 70,
}


def source_quality(url, title=""):
    try:
        host = (urlparse(url).hostname or "").lower().replace("www.", "")
    except Exception:
        host = ""
    score = 50
    for domain, weight in SOURCE_DOMAIN_WEIGHTS.items():
        if host == domain or host.endswith("." + domain):
            score = max(score, weight)
    if host.endswith(".gov") or ".gov." in host:
        score = max(score, 100)
    if host.endswith(".edu"):
        score = max(score, 82)
    if any(x in host for x in ("reddit.com", "quora.com", "facebook.com", "pinterest.com")):
        score = min(score, 35)
    return score


def rank_search_results(results):
    items, seen = [], set()
    for result in results:
        if not result.get("success"):
            continue
        for raw in result.get("results", []):
            item = dict(raw)
            url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            key = (url or title).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            item["source_quality"] = source_quality(url, title)
            items.append(item)
    items.sort(key=lambda x: x["source_quality"], reverse=True)
    return items


def run_research(prompt, task):
    """Search, rank, and fetch real page text for the best few sources."""
    max_results = task["max_results"] or 5
    results = [internet_search(q, max_results) for q in build_research_queries(prompt, task)]
    ranked = rank_search_results(results)[:10]

    top = ranked[:3]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for item, text in zip(top, pool.map(lambda i: fetch_page_text(i["url"]), top)):
            item["page_text"] = text
    return ranked


def format_research_context(ranked):
    if not ranked:
        return "NONE"
    blocks = []
    for i, x in enumerate(ranked, 1):
        block = (
            f"[{i}] {x.get('title', 'Untitled')}\n"
            f"URL: {x.get('url', '')}\n"
            f"Source quality: {x.get('source_quality', 50)}/100\n"
            f"Snippet: {x.get('snippet', '')}"
        )
        if x.get("page_text"):
            block += f"\nPage text: {x['page_text']}"
        blocks.append(block)
    return "\n\n".join(blocks)


def format_sources(ranked, count=10):
    lines = [f"{i}. [{x.get('title') or x['url']}]({x['url']})" for i, x in enumerate(ranked[:count], 1) if x.get("url")]
    return "\n\n**Sources:**\n" + "\n".join(lines) if lines else ""


# ============================================================
# OLLAMA
# ============================================================

class OllamaError(Exception):
    pass


_model_cache = {"t": 0.0, "names": None}


def get_installed_models(force=False):
    """Return the set of installed model names, or None if Ollama is unreachable."""
    now = time.time()
    if not force and now - _model_cache["t"] < 30 and _model_cache["names"] is not None:
        return _model_cache["names"]
    try:
        with urllib.request.urlopen(OLLAMA_BASE + "/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = {m.get("name", "") for m in data.get("models", [])}
        _model_cache.update(t=now, names=names)
        return names
    except Exception:
        _model_cache.update(t=now, names=None)
        return None


def model_installed(model, names):
    return model in names or (":" not in model and model + ":latest" in names)


def resolve_model(brain_key):
    """Return (brain_key_to_use, model). Falls back to any installed brain."""
    names = get_installed_models(force=True)
    if names is None:
        raise OllamaError(
            f"Cannot reach Ollama at {OLLAMA_BASE}. Start Ollama "
            "(open the Ollama app, or run 'ollama serve') and try again."
        )
    wanted = BRAINS[brain_key]["model"]
    if model_installed(wanted, names):
        return brain_key, wanted
    for key, brain in BRAINS.items():
        if model_installed(brain["model"], names):
            return key, brain["model"]
    raise OllamaError(
        "None of ULTRON's models are installed in Ollama. Installed: "
        f"{', '.join(sorted(names)) or 'nothing'}. Install one, e.g.: ollama pull {wanted}"
    )


def call_ollama(model, prompt, images=None):
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.3},   # lower = fewer invented details
    }
    if images:
        body["images"] = images            # base64 strings; vision models only
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        raise OllamaError(f"Ollama returned HTTP {e.code} for model '{model}': {body}")
    except urllib.error.URLError as e:
        raise OllamaError(f"Cannot reach Ollama at {OLLAMA_BASE}: {e.reason}")
    except (TimeoutError, socket.timeout):
        raise OllamaError(f"Ollama took longer than {OLLAMA_TIMEOUT}s to answer with '{model}'.")
    except (ConnectionError, json.JSONDecodeError) as e:
        raise OllamaError(f"Bad response from Ollama: {e}")
    return result.get("response", "")


# ============================================================
# ATTACHMENTS (images, video frames, documents)
# ============================================================

VISION_BRAIN = "apex"            # gemma3 can look at images
MAX_ATTACHMENTS = 8
MAX_IMAGES = 12
MAX_FILE_TEXT = 14000            # characters of each document passed to the model

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
CODE_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".py", ".java", ".c", ".cpp", ".h", ".cs", ".go",
                   ".rs", ".php", ".rb", ".sh", ".bat", ".ps1", ".sql", ".kt", ".swift", ".ino",
                   ".html", ".htm", ".css"}
TEXT_EXTENSIONS = CODE_EXTENSIONS | {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml",
                                     ".toml", ".ini", ".cfg", ".log", ".r", ".m"}


def extract_pdf_text(raw):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("PDF reading needs the 'pypdf' package. Run: pip install pypdf")
    reader = PdfReader(io.BytesIO(raw))
    pages = []
    for number, page in enumerate(reader.pages[:60], 1):
        pages.append(f"--- Page {number} ---\n{page.extract_text() or ''}")
    return "\n".join(pages)


def extract_docx_text(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    lines = []
    for paragraph in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        pieces = re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", paragraph, flags=re.S)
        text = "".join(htmllib.unescape(p) for p in pieces)
        if text.strip():
            lines.append(text)
    return "\n".join(lines)


def extract_pptx_text(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        slides = sorted(
            (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.findall(r"\d+", n)[-1]),
        )
        out = []
        for number, name in enumerate(slides, 1):
            xml = z.read(name).decode("utf-8", "ignore")
            texts = [htmllib.unescape(t) for t in re.findall(r"<a:t(?: [^>]*)?>(.*?)</a:t>", xml, flags=re.S)]
            out.append(f"--- Slide {number} ---\n" + " ".join(texts))
    return "\n".join(out)


def extract_xlsx_text(raw):
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("Excel reading needs the 'openpyxl' package. Run: pip install openpyxl")
    workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    out = []
    for sheet in workbook.worksheets[:5]:
        out.append(f"--- Sheet: {sheet.title} ---")
        for row_number, row in enumerate(sheet.iter_rows(values_only=True)):
            if row_number >= 200:
                out.append("... (more rows not shown)")
                break
            out.append(" | ".join("" if c is None else str(c) for c in row))
    return "\n".join(out)


def extract_video_frames(raw, count=6):
    """Sample frames evenly across the video. Returns (list_of_base64_jpegs, seconds_or_None)."""
    try:
        import cv2
    except ImportError:
        raise RuntimeError("Video analysis needs OpenCV. Run: pip install opencv-python")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        handle.write(raw)
        path = handle.name
    try:
        capture = cv2.VideoCapture(path)
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        if total <= 0:
            raise RuntimeError("Could not read this video.")
        frames = []
        for k in range(count):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(total * (k + 0.5) / count))
            ok, frame = capture.read()
            if not ok:
                continue
            height, width = frame.shape[:2]
            if width > 768:
                frame = cv2.resize(frame, (768, int(height * 768 / width)))
            ok, buffer = cv2.imencode(".jpg", frame)
            if ok:
                frames.append(base64.b64encode(buffer.tobytes()).decode("ascii"))
        capture.release()
        if not frames:
            raise RuntimeError("Could not read any frames from this video.")
        return frames, (total / fps if fps else None)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _add_text(out, name, text):
    text = (text or "").strip()
    if not text:
        out["notes"].append(f"{name} has no readable text (a scanned file?)")
        return
    if len(text) > MAX_FILE_TEXT:
        text = text[:MAX_FILE_TEXT] + "\n[... file truncated ...]"
    out["texts"].append((name, text))


def process_attachments(attachments):
    """Turn UI attachments into {images, texts, notes, has_code}."""
    out = {"images": [], "texts": [], "notes": [], "has_code": False}
    for item in (attachments or [])[:MAX_ATTACHMENTS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "file")[:120]
        mime = str(item.get("type") or "").lower()
        ext = os.path.splitext(name)[1].lower()
        b64 = item.get("data") or ""
        try:
            raw = base64.b64decode(b64)
        except Exception:
            out["notes"].append(f"{name} could not be decoded")
            continue
        if not raw:
            out["notes"].append(f"{name} was empty")
            continue
        try:
            if mime.startswith("image/") or ext in IMAGE_EXTENSIONS:
                if len(out["images"]) < MAX_IMAGES:
                    out["images"].append(b64)
                else:
                    out["notes"].append(f"{name} skipped (image limit is {MAX_IMAGES})")
            elif mime.startswith("video/") or ext in VIDEO_EXTENSIONS:
                frames, seconds = extract_video_frames(raw)
                frames = frames[:max(0, MAX_IMAGES - len(out["images"]))]
                out["images"].extend(frames)
                length = f" ({seconds:.0f}s)" if seconds else ""
                out["texts"].append((name, f"Video{length}. {len(frames)} frames sampled evenly from "
                                           "start to end are attached as images, in order."))
            elif ext == ".pdf" or mime == "application/pdf":
                _add_text(out, name, extract_pdf_text(raw))
            elif ext == ".docx":
                _add_text(out, name, extract_docx_text(raw))
            elif ext == ".pptx":
                _add_text(out, name, extract_pptx_text(raw))
            elif ext in (".xlsx", ".xlsm"):
                _add_text(out, name, extract_xlsx_text(raw))
            elif mime.startswith("audio/") or ext in AUDIO_EXTENSIONS:
                out["notes"].append(f"{name}: audio files are not supported yet")
            elif ext in TEXT_EXTENSIONS or mime.startswith("text/") or mime in ("application/json", "application/xml"):
                _add_text(out, name, raw.decode("utf-8", errors="replace"))
                if ext in CODE_EXTENSIONS:
                    out["has_code"] = True
            else:
                out["notes"].append(f"{name}: this file type is not supported")
        except RuntimeError as e:
            out["notes"].append(f"{name}: {e}")
        except Exception as e:
            out["notes"].append(f"{name} could not be read ({e})")
    return out


def route_for_attachments(att, fallback):
    if att["images"]:
        return VISION_BRAIN
    if att["texts"]:
        return "forge" if att["has_code"] else "apex"
    return fallback


def clean_model_answer(answer):
    answer = re.sub(
        r"<think>.*?</think>",
        "",
        answer or "",
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()

    # Protect code blocks from Markdown cleanup.
    code_blocks = []

    def protect_code(match):
        code_blocks.append(match.group(0))
        return f"ULTRONCODEBLOCK{len(code_blocks) - 1}END"

    answer = re.sub(
        r"```[\s\S]*?```",
        protect_code,
        answer,
    )

    # Remove unwanted backslashes before Markdown formatting.
    answer = re.sub(r"\\+(?=[*_`\-])", "", answer)

    # Remove the model's Sources section.
    # The application appends its own source links afterward.
    answer = re.sub(
        r"(?im)^[ \t]*(?:\*\*)?sources:?(?:\*\*)?[ \t]*$"
        r"[\s\S]*\Z",
        "",
        answer,
    ).strip()

    # Restore code blocks exactly as they were.
    for index, block in enumerate(code_blocks):
        answer = answer.replace(
            f"ULTRONCODEBLOCK{index}END",
            block,
        )

    return answer.strip()


# ============================================================
# ASK ULTRON
# ============================================================

def ask_ultron(prompt, attachments=None, history=None):
    """Returns (answer_text, ok, brain_key_used).

    attachments: list of {name, type, data(base64)} sent by the web UI.
    history:     optional list of {role, content} for THIS conversation (the UI keeps
                 one history per conversation); falls back to the shared history.
    """
    global current_brain

    has_attachments = bool(attachments)
    att = process_attachments(attachments)

    with state_lock:
        task = classify_task(prompt)
        if brain_mode == "auto":
            current_brain = route_auto_brain(prompt, task)
            if has_attachments:
                current_brain = route_for_attachments(att, current_brain)
        requested = current_brain
        if att["images"]:
            requested = VISION_BRAIN        # only the vision brain can look at images
        learned_name = learn_user_identity(prompt)

        # history BEFORE adding the current question, truncated so old answers
        # can't dominate the new one
        source = conversation_history if history is None else history
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:500]}" for m in source[-6:]
        )
    # Handle identity facts directly instead of asking the language model.
    if learned_name:
        if learned_name.lower() == CREATOR_NAME.lower():
            identity_answer = (
                f"Got it, {learned_name}. I'll use that name in this session "
                "and recognize it as ULTRON's configured creator."
            )
        else:
            identity_answer = (
                f"Nice to meet you, {learned_name}. I'll use that name "
                "during this session."
            )
    else:
        identity_answer = answer_identity_question(prompt, requested)

    if identity_answer is not None:
        if history is None:
            with state_lock:
                conversation_history.append(
                    {"role": "user", "content": prompt}
                )
                conversation_history.append(
                    {"role": "assistant", "content": identity_answer}
                )
                del conversation_history[:-20]

        return identity_answer, True, requested
    try:
        used, model = resolve_model(requested)
    except OllamaError as e:
        print(f"[ULTRON] {e}")
        return f"ULTRON could not reach its language model.\n\n{e}", False, requested

    if att["images"] and used != VISION_BRAIN:
        vision = BRAINS[VISION_BRAIN]
        return (f"Image and video analysis needs the {vision['name']} brain, but its model "
                f"'{vision['model']}' is not installed. Run: ollama pull {vision['model']}"), False, used

    needs_web = should_search(prompt, task) and not has_attachments
    ranked = run_research(prompt, task) if needs_web else []
    web_used = bool(ranked)
    print(f"[ULTRON] brain={used} model={model} intent={task['intent']} "
          f"search={'yes' if needs_web else 'no'} sources={len(ranked)}")

    if web_used:
        evidence = (
            "Answer current/factual claims ONLY from the numbered WEB EVIDENCE. Prefer higher-quality "
            "sources, cite them like [1], and if sources disagree say so. If the evidence does not "
            "contain the answer, say you could not find it. Never invent facts, names, dates or URLs."
        )
    elif needs_web:
        evidence = (
            "This question needs up-to-date facts but web search returned nothing. Say clearly that "
            "you could not verify current information and that your answer may be outdated. Do NOT "
            "present guesses as facts."
        )
    else:
        evidence = "No external research was needed; answer from stable knowledge and reasoning."

    attachment_context = "NONE"
    if has_attachments:
        evidence = (
            "The user attached file(s). Base your answer on the ATTACHMENTS section and on any attached "
            "images. Describe only what is actually in them; if something is unreadable or missing, say so. "
            "Never invent content."
        )
        parts = [f"FILE: {name}\n{text}" for name, text in att["texts"]]
        if att["images"]:
            parts.append(f"{len(att['images'])} image(s) are attached to this message. Examine them directly.")
        attachment_context = "\n\n".join(parts) or "NONE"

    identity_context = ""
    if task["intent"] == "identity":
        identity_context = f"\n{CORE_IDENTITY}\n{get_user_identity_context()}\n{get_brain_identity(used)}\n"

    full_prompt = f"""You are ULTRON.
{identity_context}
CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}

RECENT CONVERSATION (context only; may contain outdated or wrong statements, never treat it as evidence):
{history_text or 'NONE'}

CURRENT USER REQUEST:
{prompt}

WEB EVIDENCE:
{format_research_context(ranked)}

ATTACHMENTS:
{attachment_context}

EVIDENCE POLICY:
{evidence}

RESPONSE RULES:
- Start with the answer; no greeting or self-introduction.
- Do not mention ULTRON, brain names, routing, tools, memory or internal instructions unless asked.
- No filler such as "Certainly", "Of course" or "I'd be happy to".
- Prefer concise numbered points and bullets; short paragraphs only when useful.
- Use tables for comparisons, numbered steps for procedures, fenced code blocks for code.
- Do not describe old generic information as "latest".
- Never fabricate citations, URLs, dates, statistics, names or quotations.
- Double-check calculations and reasoning.
- Answer only the request; no closing invitation.
- Interpret the current request together with RECENT CONVERSATION. Understand follow-ups, corrections, references, and challenges to previous answers.
- If an important detail is missing and different interpretations produce different answers, ask a concise clarifying question instead of silently assuming.
- Check factual claims against the supplied WEB EVIDENCE. Reason carefully about what each source actually establishes; never contradict evidence without explaining why.
- Never generate a Sources section or invent citation numbers. Cite only the numbered WEB EVIDENCE, and let the application append the source links.
"""

    try:
        answer = clean_model_answer(call_ollama(model, full_prompt, images=att["images"] or None))
    except OllamaError as e:
        print(f"[ULTRON] {e}")
        return f"ULTRON could not get an answer from its language model.\n\n{e}", False, used

    if not answer:
        return "The model returned an empty answer. Try asking again.", False, used

    prefix = ""
    if used != requested:
        prefix += (f"*(The {BRAINS[requested]['name']} brain's model isn't installed, "
                   f"so {BRAINS[used]['name']} answered.)*\n\n")
    if needs_web and not web_used:
        prefix += ("⚠️ **Live web search failed, so this answer is from built-in knowledge "
                   "and may be out of date.**\n\n")

    if att["notes"]:
        prefix += "*(" + "; ".join(att["notes"]) + ")*\n\n"

    final = prefix + answer + (format_sources(ranked) if web_used else "")

    # Only successful exchanges are remembered. When the web UI sends its own
    # per-conversation history, the shared history is left alone.
    if history is None:
        with state_lock:
            conversation_history.append({"role": "user", "content": prompt})
            conversation_history.append({"role": "assistant", "content": answer})
            del conversation_history[:-20]

    return final, True, used


# ============================================================
# HTTP SERVER
# ============================================================

class ULTRONHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # keep the console readable; ULTRON prints its own status lines

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_REQUEST_BYTES:
            raise ValueError("Request too large")
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8")) if body else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ---------------- GET ----------------

    def do_GET(self):
        path = self.path

        # Serve static interface assets
        path = urlparse(self.path).path

        static_assets = {
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "application/javascript; charset=utf-8"),
            "/website-studio.png": ("website-studio.png", "image/png"),
        }

        if path in static_assets:
            filename, content_type = static_assets[path]
            file_path = os.path.join(BASE_DIR, filename)

            try:
                with open(file_path, "rb") as f:
                    content = f.read()

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except OSError:
                self.send_error(404, "Static asset not found")

            return


        if path == "/":
            try:
                with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Could not load index.html: {e}")
            return

        if path == "/internet":
            self.send_json({"success": True, **get_internet_status()})
            return

        if path.startswith("/search"):
            params = urllib.parse.parse_qs(urlparse(path).query)
            query = params.get("q", [""])[0].strip()
            if not query:
                self.send_json({"success": False, "error": "Missing search query."}, 400)
                return
            self.send_json(web_search(query))
            return

        if path == "/models":
            names = get_installed_models(force=True)
            if names is None:
                self.send_json({"success": False, "ollama_reachable": False,
                                "error": f"Cannot reach Ollama at {OLLAMA_BASE}"})
                return
            self.send_json({
                "success": True,
                "ollama_reachable": True,
                "installed": sorted(names),
                "missing": [b["model"] for b in BRAINS.values() if not model_installed(b["model"], names)],
            })
            return

        if path == "/brain":
            brain = BRAINS[current_brain]
            self.send_json({"success": True, "ultron": "ULTRON", "mode": brain_mode,
                            "brain": current_brain, "name": brain["name"],
                            "role": brain["role"], "capabilities": brain["capabilities"]})
            return

        if path == "/user":
            self.send_json({"success": True, "user_known": USER_NAME is not None, "name": USER_NAME})
            return

        if path == "/health":
            self.send_json({"status": "online", "ultron": True, "brain": current_brain,
                            "user_known": USER_NAME is not None,
                            "ollama_reachable": get_installed_models() is not None})
            return

        self.send_json({"success": False, "error": "Endpoint not found"}, 404)

    # ---------------- POST ----------------

    def do_POST(self):
        try:
            data = self.read_json()
        except Exception:
            self.send_json({"success": False, "error": "Invalid or too-large request (limit 90 MB)."}, 400)
            return

        if self.path == "/switch":
            self.send_json(switch_brain(data.get("brain", "")))
            return

        if self.path == "/ask":
            prompt = (data.get("prompt") or "").strip()
            attachments = data.get("attachments") if isinstance(data.get("attachments"), list) else []
            if not prompt and attachments:
                prompt = "Please analyze the attached file(s)."
            if not prompt:
                self.send_json({"success": False, "error": "No prompt provided."}, 400)
                return

            history = None
            if isinstance(data.get("history"), list):
                history = [
                    {"role": "assistant" if m.get("role") == "assistant" else "user",
                     "content": m["content"]}
                    for m in data["history"]
                    if isinstance(m, dict) and isinstance(m.get("content"), str) and m["content"].strip()
                ]

            # brain switching is handled BEFORE the model
            detected = detect_brain_switch(prompt)
            if detected:
                result = switch_brain(detected)
                if not result.get("success"):
                    self.send_json(result, 400)
                    return

                if brain_mode == "auto":
                    resp_brain, resp_name = "nexus", "ULTRON NEXUS"
                    resp_role = "Automatic brain routing"
                    resp_caps = "Selects Velocity, Forge, Apex, or Titan according to each task."
                    resp_text = result["message"]
                else:
                    b = BRAINS[current_brain]
                    resp_brain, resp_name = current_brain, b["name"]
                    resp_role, resp_caps = b["role"], b["capabilities"]
                    resp_text = f"Switched to {b['name']}.\n\nRole: {b['role']}\nCapabilities: {b['capabilities']}"

                self.send_json({
                    "success": True, "type": "brain_switch", "mode": brain_mode,
                    "mode_name": "ULTRON NEXUS" if brain_mode == "auto" else resp_name,
                    "brain": resp_brain, "brain_name": resp_name,
                    "role": resp_role, "capabilities": resp_caps, "response": resp_text,
                })
                return

            answer, ok, used = ask_ultron(prompt, attachments, history)
            brain = BRAINS[used]
            self.send_json({
                "success": ok,
                "type": "response" if ok else "error",
                "mode": brain_mode,
                "mode_name": "ULTRON NEXUS" if brain_mode == "auto" else brain["name"],
                "brain": used,
                "brain_name": brain["name"],
                "response": answer,
            })
            return

        self.send_json({"success": False, "error": "Endpoint not found"}, 404)


# ============================================================
# START ULTRON
# ============================================================

def main():
    print("\n" + "=" * 60)
    print("                    ULTRON")
    print("=" * 60 + "\n")
    print("ULTRON ONLINE\n")
    print(f"Creator : {CREATOR_NAME}")
    print("System  : Personal AI\n")
    brain = BRAINS[current_brain]
    print(f"Brain   : {brain['name']}")
    print(f"Mode    : {'ULTRON NEXUS' if brain_mode == 'auto' else brain['name']}")
    print(f"Role    : {brain['role']}\n")
    print(f"Server  : http://{HOST}:{PORT}\n")
    print("User    : Unknown\n")
    print("Web     : DuckDuckGo + Wikipedia fallback\n")

    names = get_installed_models(force=True)
    if names is None:
        print(f"!! Ollama is NOT reachable at {OLLAMA_BASE}. Start Ollama before asking questions.\n")
    else:
        print("Brains:")
        for b in BRAINS.values():
            status = "installed" if model_installed(b["model"], names) else "MISSING -> ollama pull " + b["model"]
            print(f"  {b['name']:<9} {b['model']:<14} {status}")
        print()

    print("=" * 60 + "\n")

    server = ThreadingHTTPServer((HOST, PORT), ULTRONHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nULTRON shutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
