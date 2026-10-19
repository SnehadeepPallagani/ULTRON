import urllib.request
import urllib.parse
from html.parser import HTMLParser


# ============================================================
# SEARCH RESULT PARSER
# ============================================================

class SearchResultParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.results = []

        self.current_title = ""
        self.current_url = ""
        self.current_snippet = ""

        self.in_result = False
        self.in_title = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):

        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "")

        if tag == "div" and "result" in class_name.split():
            self.in_result = True

        if tag == "a":
            if "result__a" in class_name.split():
                self.in_title = True
                self.current_url = attrs_dict.get("href", "")

        if tag in ("a", "div"):
            if "result__snippet" in class_name.split():
                self.in_snippet = True

    def handle_data(self, data):

        text = data.strip()

        if not text:
            return

        if self.in_title:
            self.current_title += text + " "

        elif self.in_snippet:
            self.current_snippet += text + " "

    def handle_endtag(self, tag):

        if tag == "a" and self.in_title:
            self.in_title = False

        if self.in_snippet:

            if tag in ("a", "div"):

                self.in_snippet = False

                if self.current_title.strip():

                    self.results.append({
                        "title": self.current_title.strip(),
                        "url": self.current_url,
                        "snippet": self.current_snippet.strip()
                    })

                    self.current_title = ""
                    self.current_url = ""
                    self.current_snippet = ""

                    self.in_result = False


# ============================================================
# SEARCH PROVIDER BASE
# ============================================================

class SearchProvider:

    name = "Unknown"

    def search(self, query, max_results=5):
        raise NotImplementedError


# ============================================================
# DUCKDUCKGO
# ============================================================

class DuckDuckGoSearchProvider(SearchProvider):

    name = "DuckDuckGo"

    def search(self, query, max_results=5):

        if not query:
            return {
                "success": False,
                "error": "Search query is empty."
            }

        encoded_query = urllib.parse.quote_plus(query)

        search_url = (
            "https://html.duckduckgo.com/html/?q="
            + encoded_query
        )

        request = urllib.request.Request(
            search_url,
            headers={
                "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/154.0 Safari/537.36"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=15
        ) as response:

            html = response.read().decode(
                "utf-8",
                errors="ignore"
            )

        parser = SearchResultParser()
        parser.feed(html)

        results = parser.results[:max_results]

        return {
            "success": True,
            "query": query,
            "provider": self.name,
            "result_count": len(results),
            "results": results
        }


# ============================================================
# ULTRON INTERNET LAYER
# ============================================================

INTERNET_PROVIDERS = {
    "duckduckgo": DuckDuckGoSearchProvider()
}

ACTIVE_SEARCH_PROVIDER = "duckduckgo"


# ============================================================
# INTERNET STATUS
# ============================================================

def get_internet_status():

    provider = INTERNET_PROVIDERS.get(
        ACTIVE_SEARCH_PROVIDER
    )

    return {
        "online": True,
        "layer": "ULTRON Internet Layer",
        "active_search_provider":
            provider.name if provider else None,
        "available_search_providers": [
            p.name
            for p in INTERNET_PROVIDERS.values()
        ]
    }


# ============================================================
# QUERY FALLBACK GENERATOR
# ============================================================

def build_fallback_queries(query):

    query = query.strip()

    queries = []

    # Original query
    queries.append(query)

    # Remove common conversational words
    simplified = query

    removable_words = [
        "what are",
        "what is",
        "tell me about",
        "show me",
        "give me",
        "can you explain",
        "please explain",
        "latest",
        "currently",
        "today"
    ]

    for word in removable_words:

        simplified = simplified.replace(
            word,
            ""
        )

    simplified = " ".join(
        simplified.split()
    ).strip()

    if simplified and simplified.lower() != query.lower():
        queries.append(simplified)

    # Add current-year context for likely current queries
    if any(
        word in query.lower()
        for word in [
            "latest",
            "current",
            "today",
            "recent",
            "new"
        ]
    ):

        current_year_query = (
            simplified
            + " 2026"
        ).strip()

        if current_year_query not in queries:
            queries.append(current_year_query)

    # Remove duplicates
    unique_queries = []

    for item in queries:

        if item and item.lower() not in [
            q.lower()
            for q in unique_queries
        ]:

            unique_queries.append(item)

    return unique_queries[:3]


# ============================================================
# INTERNET SEARCH WITH RETRY
# ============================================================

def internet_search(query, max_results=5):

    if not query:

        return {
            "success": False,
            "error": "Search query is empty.",
            "internet_layer": True
        }

    provider = INTERNET_PROVIDERS.get(
        ACTIVE_SEARCH_PROVIDER
    )

    if provider is None:

        return {
            "success": False,
            "query": query,
            "internet_layer": True,
            "error":
                "No active Internet search provider."
        }

    queries = build_fallback_queries(query)

    last_error = None

    for attempt, search_query in enumerate(
        queries,
        start=1
    ):

        try:

            result = provider.search(
                search_query,
                max_results
            )

            if result.get("success"):

                results = result.get(
                    "results",
                    []
                )

                if results:

                    result["internet_layer"] = True
                    result["original_query"] = query
                    result["attempt"] = attempt

                    return result

            last_error = (
                f"No results for: {search_query}"
            )

        except Exception as e:

            last_error = str(e)

    return {
        "success": False,
        "query": query,
        "internet_layer": True,
        "provider": provider.name,
        "error": last_error or "No search results found.",
        "attempted_queries": queries,
        "result_count": 0,
        "results": []
    }


# ============================================================
# COMPATIBILITY WRAPPER
# ============================================================

def web_search(query, max_results=5):

    return internet_search(
        query,
        max_results
    )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("ULTRON INTERNET LAYER")
    print("----------------------------------------")

    print("Status:")
    print(get_internet_status())

    print("\nTesting Internet Search...")
    print("----------------------------------------")

    query = input("Search: ").strip()

    result = internet_search(
        query,
        max_results=5
    )

    print("\nRESULT")
    print("----------------------------------------")

    if not result.get("success"):

        print("Search failed:")
        print(result.get("error"))

        if result.get("attempted_queries"):
            print(
                "\nAttempted queries:"
            )

            for q in result["attempted_queries"]:
                print("-", q)

    else:

        print(
            "Provider:",
            result.get("provider")
        )

        print(
            "Original query:",
            result.get("original_query")
        )

        print(
            "Successful query:",
            result.get("query")
        )

        print(
            "Attempt:",
            result.get("attempt")
        )

        print(
            "Results:",
            result.get("result_count")
        )

        for index, item in enumerate(
            result.get("results", []),
            start=1
        ):

            print(
                f"\n{index}. "
                f"{item.get('title')}"
            )

            print(
                "   URL:",
                item.get("url")
            )

            print(
                "   ",
                item.get("snippet")
            )