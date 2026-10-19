import re
from urllib.parse import urlparse

from internet import internet_search


# ============================================================
# RESEARCH ENGINE V3
# ============================================================

STATIC_PATTERNS = [
    r"\bwhat is\b",
    r"\bwhat are\b",
    r"\bexplain\b",
    r"\bdefine\b",
    r"\bmeaning of\b",
]

CURRENT_PATTERNS = [
    r"\blatest\b",
    r"\btoday\b",
    r"\bcurrently\b",
    r"\bcurrent\b",
    r"\bnow\b",
    r"\brecent\b",
    r"\bthis year\b",
    r"\b2026\b",
]

RESEARCH_PATTERNS = [
    r"\bresearch\b",
    r"\banalyze\b",
    r"\binvestigate\b",
    r"\bcompare\b",
    r"\bstudy\b",
    r"\bdevelopments\b",
    r"\btrends\b",
    r"\bdeep dive\b",
]

HIGH_ACCURACY_PATTERNS = [
    r"\bmedical\b",
    r"\bmedicine\b",
    r"\bdiagnos\w*\b",
    r"\bdrug\b",
    r"\blegal\b",
    r"\blaw\b",
    r"\bfinancial\b",
    r"\bsecurity\b",
]

BROAD_PATTERNS = [
    r"\bdevelopments\b",
    r"\btrends\b",
    r"\boverview\b",
    r"\blandscape\b",
    r"\bstate of\b",
    r"\bmajor\b",
]


# ============================================================
# HELPERS
# ============================================================

def _has_any_pattern(text, patterns):
    text = text.lower()

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def classify_task(prompt):

    text = prompt.lower().strip()

    current = _has_any_pattern(
        text,
        CURRENT_PATTERNS
    )

    research = _has_any_pattern(
        text,
        RESEARCH_PATTERNS
    )

    high_accuracy = _has_any_pattern(
        text,
        HIGH_ACCURACY_PATTERNS
    )

    broad = _has_any_pattern(
        text,
        BROAD_PATTERNS
    )

    score = 0
    signals = []

    if current:
        score += 4
        signals.append("current_or_time_sensitive")

    if research:
        score += 3
        signals.append("research_request")

    if broad:
        score += 2
        signals.append("broad_research_topic")

    if high_accuracy:
        score += 3
        signals.append("high_accuracy_domain")

    # Current/broad topics should normally be researched.
    research_required = (
        score >= 4
        or research
        or broad
    )

    if high_accuracy:
        depth = "deep"

    elif research_required and (
        research or broad
    ):
        depth = "deep"

    elif research_required:
        depth = "quick"

    else:
        depth = "none"

    if high_accuracy:
        max_results = 8

    elif depth == "deep":
        max_results = 8

    else:
        max_results = 5

    return {
        "intent": "research" if research_required else "general",
        "research_required": research_required,
        "research_depth": depth,
        "research_score": score,
        "signals": signals,
        "high_accuracy": high_accuracy,
        "broad": broad,
        "max_results": max_results
    }


# ============================================================
# QUERY PLANNER
# ============================================================

def build_research_queries(prompt, plan):

    queries = []

    base = prompt.strip()

    queries.append(base)

    if plan["research_depth"] == "deep":

        queries.append(
            f"{base} 2026 official"
        )

        if "AI" in base or "ai" in base.lower():

            queries.append(
                "latest AI developments 2026 official"
            )

            queries.append(
                "latest AI model releases 2026"
            )

            queries.append(
                "latest AI research breakthroughs 2026"
            )

    elif plan["research_depth"] == "quick":

        queries.append(
            f"{base} 2026"
        )

    # Remove duplicates while preserving order.

    unique = []

    for query in queries:

        if query not in unique:
            unique.append(query)

    return unique


# ============================================================
# SOURCE QUALITY
# ============================================================

SOURCE_DOMAIN_WEIGHTS = {

    # Official / government
    "gov": 100,
    "edu": 95,

    # Research
    "arxiv.org": 95,
    "nature.com": 95,
    "science.org": 95,
    "acm.org": 90,
    "ieee.org": 90,

    # Major technology companies
    "openai.com": 95,
    "google.com": 95,
    "deepmind.google": 95,
    "microsoft.com": 90,
    "meta.com": 90,
    "anthropic.com": 95,

    # Major news
    "reuters.com": 85,
    "bloomberg.com": 85,
    "bbc.com": 80,
    "nytimes.com": 80,

    # Technical publications
    "techcrunch.com": 75,
    "arstechnica.com": 75,
    "theverge.com": 70,
}


def source_quality(result):

    url = result.get("url", "")

    title = result.get(
        "title",
        ""
    ).lower()

    parsed = urlparse(url)

    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    score = 50

    # Direct domain matching
    for known_domain, weight in SOURCE_DOMAIN_WEIGHTS.items():

        if domain == known_domain or domain.endswith(
            "." + known_domain
        ):
            score = max(
                score,
                weight
            )

    # Government / education domains
    if domain.endswith(".gov"):
        score = max(score, 100)

    if domain.endswith(".edu"):
        score = max(score, 95)

    # Avoid obvious low-quality signals
    bad_terms = [
        "seo",
        "casino",
        "coupon",
        "spam",
        "clickbait"
    ]

    if any(term in domain for term in bad_terms):
        score -= 30

    if not title:
        score -= 5

    return max(
        0,
        min(score, 100)
    )


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def normalize_result(result):

    if not isinstance(result, dict):
        return None

    title = (
        result.get("title")
        or result.get("name")
        or "Untitled source"
    )

    url = (
        result.get("url")
        or result.get("link")
        or ""
    )

    snippet = (
        result.get("snippet")
        or result.get("description")
        or result.get("body")
        or ""
    )

    if not url:
        return None

    normalized = {
        "title": str(title).strip(),
        "url": str(url).strip(),
        "snippet": str(snippet).strip()
    }

    normalized["quality"] = source_quality(
        normalized
    )

    return normalized


# ============================================================
# SEARCH WITH RETRIES
# ============================================================

def search_with_retries(queries, max_results=8):

    all_results = []

    attempts = []

    for query in queries:

        try:

            response = internet_search(
                query,
                max_results=max_results
            )

            attempts.append({
                "query": query,
                "success": True
            })

            if isinstance(response, dict):

                results = response.get(
                    "results",
                    []
                )

            elif isinstance(response, list):

                results = response

            else:

                results = []

            if results:

                for item in results:

                    normalized = normalize_result(
                        item
                    )

                    if normalized:
                        all_results.append(
                            normalized
                        )

            # If this query worked, continue with
            # additional queries for deep research.

        except Exception as error:

            attempts.append({
                "query": query,
                "success": False,
                "error": str(error)
            })

    return all_results, attempts


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_results(results):

    unique = []
    seen_urls = set()

    for result in results:

        url = result.get(
            "url",
            ""
        ).strip()

        if not url:
            continue

        normalized_url = url.lower()

        if normalized_url in seen_urls:
            continue

        seen_urls.add(
            normalized_url
        )

        unique.append(result)

    return unique


# ============================================================
# RANK RESULTS
# ============================================================

def rank_search_results(results):

    results = deduplicate_results(
        results
    )

    results.sort(
        key=lambda item: item.get(
            "quality",
            0
        ),
        reverse=True
    )

    return results


# ============================================================
# RESEARCH CONTEXT
# ============================================================

def format_research_context(results):

    if not results:
        return ""

    sections = []

    for index, result in enumerate(
        results,
        1
    ):

        title = result.get(
            "title",
            "Unknown source"
        )

        url = result.get(
            "url",
            ""
        )

        snippet = result.get(
            "snippet",
            ""
        )

        quality = result.get(
            "quality",
            0
        )

        section = f"""
SOURCE {index}

Title: {title}
URL: {url}
Quality Score: {quality}

Evidence:
{snippet}
"""

        sections.append(
            section.strip()
        )

    return "\n\n".join(
        sections
    )


# ============================================================
# MAIN RESEARCH FUNCTION
# ============================================================

def conduct_research(prompt):

    plan = classify_task(
        prompt
    )

    print("\nRESEARCH PLAN")
    print(plan)

    if not plan["research_required"]:

        return {
            "success": False,
            "research_required": False,
            "plan": plan,
            "queries": [],
            "results": [],
            "context": "",
            "attempts": []
        }

    queries = build_research_queries(
        prompt,
        plan
    )

    print("\nQUERIES")

    for query in queries:
        print(f"- {query}")

    results, attempts = search_with_retries(
        queries,
        max_results=plan["max_results"]
    )

    results = rank_search_results(
        results
    )

    # Keep the final evidence set manageable.
    results = results[
        :plan["max_results"]
    ]

    context = format_research_context(
        results
    )

    print("\nRESULTS")
    print(
        f"Sources found: {len(results)}"
    )

    for index, result in enumerate(
        results,
        1
    ):

        print(
            f"{index}. "
            f"{result['title']} "
            f"Quality {result['quality']}"
        )

    if not results:

        print(
            "\nWARNING: No web sources were obtained."
        )

    return {
        "success": bool(results),
        "research_required": True,
        "plan": plan,
        "queries": queries,
        "results": results,
        "context": context,
        "attempts": attempts
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("ULTRON RESEARCH ENGINE V3")

    query = input(
        "\nResearch: "
    ).strip()

    if query:

        result = conduct_research(
            query
        )

        print("\nFINAL RESEARCH STATUS")
        print(
            "Success:",
            result["success"]
        )

        print(
            "Sources:",
            len(result["results"])
        )