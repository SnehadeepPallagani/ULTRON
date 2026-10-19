from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request


# ================================================================
# ULTRON VIBE CODING ENGINE V3
# ================================================================
#
# Core principle:
#   understand → inspect → plan → patch → backup → apply
#   → validate → test → verify
#
# The engine never claims a change happened unless:
#   1. the target file was located,
#   2. the requested patch matched safely,
#   3. the file was written,
#   4. validation passed.
#
# Generic software changes are produced by the local Forge model
# through a strict JSON patch contract.
# ================================================================


DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen3.5:9b"

IGNORED_DIRS = {
    ".git",
    ".ultron_backups",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".cache",
}

SUPPORTED_TEXT_EXTENSIONS = {
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".md",
    ".txt",
    ".xml",
    ".yml",
    ".yaml",
}


@dataclass
class EditResult:
    success: bool
    file: str = ""
    message: str = ""
    backup: str = ""
    changed: bool = False
    verification: str = ""
    tests: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.tests is None:
            self.tests = []


class VibeCodingEngine:
    """
    Local project-aware Vibe Coding Engine.

    By default the project root is the current working directory.
    Set ULTRON_PROJECT_ROOT to override it.
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
    ):
        root = (
            project_root
            or os.environ.get("ULTRON_PROJECT_ROOT")
            or os.getcwd()
        )

        self.project_root = Path(root).expanduser().resolve()
        self.ollama_url = ollama_url
        self.model = model

        self.backup_root = self.project_root / ".ultron_backups"

    # ============================================================
    # PROJECT DISCOVERY
    # ============================================================

    def discover_project(self) -> Dict[str, Any]:
        files: List[Path] = []

        if not self.project_root.exists():
            return {
                "success": False,
                "message": f"Project root does not exist: {self.project_root}",
                "project_root": str(self.project_root),
                "files": [],
            }

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue

            try:
                relative = path.relative_to(self.project_root)
            except ValueError:
                continue

            if any(part in IGNORED_DIRS for part in relative.parts):
                continue

            files.append(path)

        files.sort(key=lambda p: str(p).lower())

        grouped = {
            "html": [],
            "css": [],
            "javascript": [],
            "python": [],
            "java": [],
            "other": [],
        }

        for path in files:
            suffix = path.suffix.lower()
            rel = str(path.relative_to(self.project_root))

            if suffix in {".html", ".htm"}:
                grouped["html"].append(rel)
            elif suffix in {".css", ".scss", ".sass"}:
                grouped["css"].append(rel)
            elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
                grouped["javascript"].append(rel)
            elif suffix == ".py":
                grouped["python"].append(rel)
            elif suffix == ".java":
                grouped["java"].append(rel)
            else:
                grouped["other"].append(rel)

        return {
            "success": True,
            "project_root": str(self.project_root),
            "total_files": len(files),
            "files": [str(p.relative_to(self.project_root)) for p in files],
            "groups": grouped,
        }

    def _score_file_for_website(self, path: Path) -> int:
        name = path.name.lower()
        score = 0

        if name == "index.html":
            score += 100
        elif path.suffix.lower() in {".html", ".htm"}:
            score += 50

        if any(token in name for token in ("home", "landing", "main")):
            score += 10

        try:
            size = path.stat().st_size
            if size > 500:
                score += 5
        except OSError:
            pass

        return score

    def _find_primary_html(self) -> Optional[Path]:
        discovery = self.discover_project()

        if not discovery.get("success"):
            return None

        html_paths = [
            self.project_root / rel
            for rel in discovery["groups"]["html"]
        ]

        if not html_paths:
            return None

        html_paths.sort(
            key=self._score_file_for_website,
            reverse=True,
        )

        return html_paths[0]

    def inspect_website(self) -> Dict[str, Any]:
        primary = self._find_primary_html()

        if not primary:
            return {
                "success": False,
                "message": "No HTML file was found in the project.",
            }

        try:
            content = primary.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = primary.read_text(encoding="utf-8-sig")
            except Exception as exc:
                return {
                    "success": False,
                    "message": f"Unable to read HTML: {exc}",
                }
        except OSError as exc:
            return {
                "success": False,
                "message": f"Unable to read HTML: {exc}",
            }

        structure = self.inspect_html_structure(content)

        return {
            "success": True,
            "file": str(primary),
            "relative_path": str(
                primary.relative_to(self.project_root)
            ),
            "lines": len(content.splitlines()),
            "characters": len(content),
            "structure": structure,
        }

    @staticmethod
    def inspect_html_structure(content: str) -> Dict[str, Any]:
        lower = content.lower()

        def present(pattern: str) -> bool:
            return re.search(pattern, lower) is not None

        return {
            "doctype": present(r"<!doctype\s+html"),
            "html": present(r"<html\b"),
            "head": present(r"<head\b"),
            "body": present(r"<body\b"),
            "header": present(r"<header\b"),
            "nav": present(r"<nav\b"),
            "buttons": present(r"<button\b"),
            "forms": present(r"<form\b"),
            "links": present(r"<a\b"),
            "images": present(r"<img\b"),
            "scripts": present(r"<script\b"),
            "styles": present(r"<style\b") or present(r"<link[^>]+stylesheet"),
            "sections": {
                "header": present(r"<header\b"),
                "nav": present(r"<nav\b"),
                "main": present(r"<main\b"),
                "footer": present(r"<footer\b"),
                "forms": present(r"<form\b"),
            },
        }

    def inspect_file(self, relative_path: str) -> Dict[str, Any]:
        path = self._safe_project_path(relative_path)

        if not path or not path.is_file():
            return {
                "success": False,
                "message": f"File not found: {relative_path}",
            }

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            return {
                "success": False,
                "message": str(exc),
            }

        return {
            "success": True,
            "file": str(path),
            "relative_path": str(path.relative_to(self.project_root)),
            "lines": len(content.splitlines()),
            "characters": len(content),
            "content": content,
        }

    # ============================================================
    # REQUEST ANALYSIS
    # ============================================================

    def analyze_request(self, user_input: str) -> Dict[str, Any]:
        text = (user_input or "").strip()
        lower = text.lower()

        modification_signals = (
            "add ",
            "remove ",
            "delete ",
            "change ",
            "modify ",
            "improve ",
            "better ",
            "update ",
            "fix ",
            "refactor ",
            "replace ",
            "make ",
            "style ",
            "restyle ",
            "edit ",
        )

        creation_signals = (
            "build ",
            "create ",
            "develop ",
            "generate ",
            "make a website",
            "make an app",
            "make a page",
            "make me a website",
        )

        is_modify = any(
            lower.startswith(signal)
            for signal in modification_signals
        )

        if "same html" in lower or "existing website" in lower:
            is_modify = True

        target = "generic"
        action = "modify"

        if "create account" in lower or "sign up" in lower:
            target = "create_account"
            action = "modify"
        elif "navbar" in lower or "navigation bar" in lower:
            target = "navbar"
            action = "modify"
        elif (
            "website" in lower
            and ("vibecode" in lower or "vibe code" in lower)
        ):
            target = "website"
            action = "inspect_and_modify"
        elif any(
            term in lower
            for term in ("login page", "login interface", "login form")
        ):
            target = "login"
            action = "modify"
        elif any(
            term in lower
            for term in ("hero section", "hero area")
        ):
            target = "hero"
            action = "modify"
        elif any(
            term in lower
            for term in ("footer", "footer section")
        ):
            target = "footer"
            action = "modify"
        elif any(
            term in lower
            for term in ("button", "buttons")
        ):
            target = "button"
            action = "modify"
        elif lower.startswith(creation_signals):
            action = "create"
            target = (
                "website"
                if "website" in lower or "page" in lower
                else "application"
            )
        elif "vibecode" in lower or "vibe code" in lower:
            action = "inspect_and_modify"
            target = "project"

        return {
            "success": True,
            "request": text,
            "action": action,
            "target": target,
            "is_modification": is_modify or action == "modify",
            "requires_existing_project": action
            in {"modify", "inspect_and_modify"},
        }

    # ============================================================
    # FILE/PROJECT CONTEXT FOR THE PATCH MODEL
    # ============================================================

    def _select_relevant_files(
        self,
        request_text: str,
        max_files: int = 4,
    ) -> List[Path]:
        discovery = self.discover_project()

        if not discovery.get("success"):
            return []

        all_files = [
            self.project_root / rel
            for rel in discovery.get("files", [])
        ]

        lower = request_text.lower()

        def score(path: Path) -> int:
            score_value = 0
            name = path.name.lower()
            suffix = path.suffix.lower()

            if path == self._find_primary_html():
                score_value += 100

            if suffix in {".html", ".htm"}:
                score_value += 30
            elif suffix in {".css", ".scss", ".sass"}:
                score_value += 25
            elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
                score_value += 20

            keyword_groups = (
                (
                    ("navbar", "navigation", "header", "menu"),
                    ("nav", "header", "menu", "layout", "index", "app"),
                ),
                (
                    ("login", "account", "signup", "sign up"),
                    ("login", "auth", "account", "signup", "index"),
                ),
                (
                    ("hero", "landing"),
                    ("hero", "home", "landing", "index"),
                ),
            )

            for request_words, name_words in keyword_groups:
                if any(word in lower for word in request_words):
                    if any(word in name for word in name_words):
                        score_value += 25

            # Prefer small source files after the main target.
            try:
                if path.stat().st_size < 20000:
                    score_value += 5
            except OSError:
                pass

            return score_value

        ranked = sorted(
            all_files,
            key=score,
            reverse=True,
        )

        return ranked[:max_files]

    @staticmethod
    def _extract_relevant_windows(
        content: str,
        request_text: str,
        max_chars: int = 12000,
    ) -> str:
        """
        Return only the source regions most likely related to the
        requested change. This keeps Forge prompts fast while still
        giving it exact source text for targeted patches.
        """

        lines = content.splitlines()
        lower = content.lower()
        request = request_text.lower()

        keyword_map = {
            "navbar": (
                "nav", "navbar", "navigation", "menu",
                "header", "hamburger", "links"
            ),
            "navigation": (
                "nav", "navbar", "navigation", "menu",
                "header", "hamburger", "links"
            ),
            "header": (
                "header", "nav", "menu", "links"
            ),
            "account": (
                "account", "signup", "sign-up", "sign up",
                "register", "login"
            ),
            "login": (
                "login", "signin", "sign-in", "form",
                "password", "email"
            ),
            "hero": (
                "hero", "banner", "headline", "cta"
            ),
            "footer": (
                "footer", "copyright", "social"
            ),
            "button": (
                "button", "btn"
            ),
        }

        tokens = []
        for trigger, related in keyword_map.items():
            if trigger in request:
                tokens.extend(related)

        # Generic "make/fix/improve the website" gets the primary
        # structural regions rather than the entire file.
        if not tokens:
            tokens = (
                "header",
                "main",
                "footer",
                "script",
                "style",
            )

        hits = []
        for index, line in enumerate(lines):
            line_lower = line.lower()
            if any(token in line_lower for token in tokens):
                hits.append(index)

        # For HTML navbar requests, prefer complete header/nav blocks.
        block_patterns = []
        if any(word in request for word in ("navbar", "navigation", "header", "menu")):
            block_patterns.extend([
                r"<header\b.*?</header\s*>",
                r"<nav\b.*?</nav\s*>",
            ])

        chunks = []
        used = set()

        for pattern in block_patterns:
            for match in re.finditer(
                pattern,
                content,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                snippet = match.group(0).strip()
                if snippet and snippet not in used:
                    chunks.append(
                        "[RELEVANT BLOCK]\n"
                        + snippet
                        + "\n[END RELEVANT BLOCK]"
                    )
                    used.add(snippet)

        # Add small line windows around keyword hits.
        for hit in hits:
            start = max(0, hit - 35)
            end = min(len(lines), hit + 36)

            snippet = "\n".join(lines[start:end]).strip()
            if not snippet:
                continue

            wrapped = (
                f"[SOURCE LINES {start + 1}-{end}]\n"
                f"{snippet}"
            )

            if wrapped not in used:
                chunks.append(wrapped)
                used.add(wrapped)

            if sum(len(chunk) for chunk in chunks) >= max_chars:
                break

        # Always give Forge a little document context.
        if not chunks:
            chunks.append(
                "\n".join(lines[:180])
            )

        combined = "\n\n".join(chunks)

        if len(combined) <= max_chars:
            return combined

        return combined[:max_chars] + "\n[TRUNCATED]"

    def _build_project_context(
        self,
        request_text: str,
        files: List[Path],
        max_chars_per_file: int = 9000,
    ) -> str:
        parts: List[str] = []

        for path in files:
            try:
                if path.suffix.lower() not in SUPPORTED_TEXT_EXTENSIONS:
                    continue

                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )

                focused = self._extract_relevant_windows(
                    content,
                    request_text,
                    max_chars=max_chars_per_file,
                )

                relative = str(
                    path.relative_to(self.project_root)
                )

                parts.append(
                    f"===== FILE: {relative} =====\n"
                    f"{focused}\n"
                    f"===== END FILE: {relative} ====="
                )
            except OSError:
                continue

        return "\n\n".join(parts)

    # ============================================================
    # LOCAL FORGE PATCH PLANNER
    # ============================================================

    def _call_ollama(
        self,
        prompt: str,
        timeout: int = 120,
        structured_json: bool = False,
        model: Optional[str] = None,
    ) -> str:
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 512,
            },
        }

        # Ollama supports structured JSON output through the
        # `format` field. This is used for patch planning so Forge
        # cannot freely wrap the result in prose/Markdown.
        if structured_json:
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")

        req = request.Request(
            self.ollama_url,
            data=data,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=timeout) as response:
                result = json.loads(
                    response.read().decode("utf-8")
                )

            return str(
                result.get("response", "")
            ).strip()

        except error.URLError as exc:
            raise RuntimeError(
                f"Ollama connection failed: {exc}"
            ) from exc

        except TimeoutError as exc:
            raise RuntimeError(
                "Forge timed out while planning the patch."
            ) from exc

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Invalid Ollama response: {exc}"
            ) from exc

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()

        # Remove model thinking blocks when a local model emits them.
        cleaned = re.sub(
            r"<think>.*?</think>",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        # Remove common Markdown code fences.
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        ).strip()

        # Some models prefix a JSON object with a short sentence.
        # Locate the first balanced-looking JSON object.
        candidates = []

        first = cleaned.find("{")
        last = cleaned.rfind("}")

        if first >= 0 and last > first:
            candidates.append(
                cleaned[first:last + 1]
            )

        candidates.append(cleaned)

        for candidate in candidates:
            try:
                value = json.loads(candidate)

                if isinstance(value, dict):
                    return value

            except json.JSONDecodeError:
                continue

        raise ValueError(
            "Forge did not return a valid JSON patch plan."
        )

    def _build_target_context(
        self,
        user_input: str,
        files: List[Path],
    ) -> Dict[str, Any]:
        """
        Build a compact, target-aware context for Forge.

        For visual requests such as "Make the navbar better", do not
        send the whole project. Extract the exact structural region
        first, then give Forge only the source it needs to design a
        targeted patch.
        """
        analysis = self.analyze_request(user_input)
        target = analysis.get("target", "generic")

        primary = self._find_primary_html()
        candidates = [primary] if primary else []

        for path in files:
            if path not in candidates and path.is_file():
                candidates.append(path)

        for path in candidates:
            if not path or not path.is_file():
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            if path.suffix.lower() not in {".html", ".htm"}:
                continue

            relative = str(path.relative_to(self.project_root))
            blocks: List[str] = []

            if target == "navbar":
                # The current project may use <header> instead of
                # <nav>; support both without assuming a <nav> tag.
                for tag in ("header", "nav"):
                    pattern = rf"<{tag}\b[^>]*>.*?</{tag}\s*>"
                    matches = list(re.finditer(
                        pattern,
                        content,
                        flags=re.IGNORECASE | re.DOTALL,
                    ))
                    for match in matches[:2]:
                        blocks.append(
                            f"[TARGET {tag.upper()} BLOCK]\n"
                            f"{match.group(0).strip()}\n"
                            f"[END TARGET {tag.upper()} BLOCK]"
                        )

                # If there is no semantic header/nav, inspect the
                # opening portion where navigation commonly lives.
                if not blocks:
                    lines = content.splitlines()
                    top = "\n".join(lines[:220])
                    blocks.append(
                        "[TOP-OF-PAGE NAVIGATION CONTEXT]\n"
                        + top
                        + "\n[END TOP-OF-PAGE NAVIGATION CONTEXT]"
                    )

                # Include only CSS rules likely controlling the
                # navigation/header, not the entire stylesheet.
                style_matches = re.findall(
                    r"<style\b[^>]*>(.*?)</style\s*>",
                    content,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                css_chunks: List[str] = []
                css_terms = (
                    "header", "nav", "navbar", "menu", "links",
                    "logo", "button", "mobile", "hamburger"
                )

                for style in style_matches:
                    rules = re.findall(
                        r"[^{}]+\{[^{}]*\}",
                        style,
                        flags=re.DOTALL,
                    )
                    for rule in rules:
                        if any(
                            term in rule.lower()
                            for term in css_terms
                        ):
                            css_chunks.append(rule.strip())

                if css_chunks:
                    blocks.append(
                        "[RELEVANT NAVIGATION CSS]\n"
                        + "\n\n".join(css_chunks[:35])
                        + "\n[END RELEVANT NAVIGATION CSS]"
                    )

                return {
                    "target": target,
                    "relative_file": relative,
                    "context": "\n\n".join(blocks)[:9000],
                    "target_region": "header/navigation",
                }

            # Generic fallback: retain the existing focused extractor.
            focused = self._extract_relevant_windows(
                content,
                user_input,
                max_chars=18000,
            )

            return {
                "target": target,
                "relative_file": relative,
                "context": focused,
                "target_region": target,
            }

        return {
            "target": target,
            "relative_file": "",
            "context": "",
            "target_region": target,
        }

    def _deterministic_navbar_plan(self, user_input: str, relevant_files: List[Path]) -> Optional[Dict[str, Any]]:
        """Create a conservative navbar improvement without requiring an LLM.

        This is intentionally used for broad visual requests such as
        "make the navbar better". The engine already knows the target is
        navigation, so there is no reason to make a local 9B model invent a
        JSON patch for a simple, bounded CSS enhancement.
        """
        analysis = self.analyze_request(user_input)
        if analysis.get("target") != "navbar":
            return None

        lower = user_input.lower()
        visual_terms = ("better", "improve", "enhance", "modern", "clean", "polish", "style", "design")
        if not any(term in lower for term in visual_terms):
            return None

        primary = self._find_primary_html()
        if not primary or not primary.is_file():
            return None

        try:
            content = primary.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        if "/* ULTRON NAVBAR ENHANCEMENT V3.4 */" in content:
            return {
                "summary": "Navbar enhancement is already present; no duplicate patch required.",
                "patches": [],
                "tests": ["Verify the existing navbar enhancement marker remains present."],
            }

        css = """<style id="ultron-navbar-enhancement-v34">\n/* ULTRON NAVBAR ENHANCEMENT V3.4 */\nheader {\n  position: sticky;\n  top: 0;\n  z-index: 1000;\n  backdrop-filter: blur(12px);\n  -webkit-backdrop-filter: blur(12px);\n  border-bottom: 1px solid rgba(255, 180, 0, 0.28);\n  transition: box-shadow 0.2s ease, border-color 0.2s ease;\n}\nheader a {\n  transition: color 0.2s ease, opacity 0.2s ease, transform 0.2s ease;\n}\nheader a:hover {\n  opacity: 1;\n  transform: translateY(-1px);\n}\nheader button {\n  transition: transform 0.2s ease, box-shadow 0.2s ease;\n}\nheader button:hover {\n  transform: translateY(-1px);\n}\n</style>"""

        return {
            "summary": "Add a small scoped visual/UX enhancement to the existing header navigation without changing its links or structure.",
            "patches": [{
                "file": str(primary.relative_to(self.project_root)),
                "old_text": "</head>",
                "new_text": css + "\n</head>",
                "reason": "Improve the existing header navigation with sticky positioning, subtle backdrop treatment, clearer separation, and restrained hover motion while preserving existing markup and links.",
            }],
            "tests": [
                "Verify the HTML still contains one closing head tag.",
                "Verify the navbar enhancement marker is present exactly once.",
                "Verify existing header links and buttons remain present.",
            ],
        }

    def plan_patch(
        self,
        user_input: str,
        relevant_files: List[Path],
    ) -> Dict[str, Any]:
        deterministic = self._deterministic_navbar_plan(user_input, relevant_files)
        if deterministic is not None:
            return deterministic

        target_context = self._build_target_context(
            user_input,
            relevant_files,
        )

        project_context = target_context.get("context", "")
        target = target_context.get("target", "generic")
        target_file = target_context.get("relative_file", "")

        file_list = [
            str(path.relative_to(self.project_root))
            for path in relevant_files
        ]

        if target_file and target_file not in file_list:
            file_list.insert(0, target_file)

        system = f"""
You are Forge, the coding brain inside ULTRON.

You are modifying an EXISTING local software project.

USER REQUEST:
{user_input}

DETECTED TARGET:
{target}

PRIMARY TARGET FILE:
{target_file}

AVAILABLE FILES:
{json.dumps(file_list, indent=2)}

TARGET-AWARE SOURCE CONTEXT:
{project_context}

TASK:
Design a SAFE, TARGETED patch for the user's request.

CRITICAL RULES:
1. Preserve unrelated functionality.
2. Do not regenerate an entire HTML file.
3. Only modify files shown above.
4. Every patch MUST use exact old_text -> new_text replacement.
5. old_text MUST be copied exactly from the supplied source context.
6. Each old_text MUST match exactly once in the real file.
7. Keep the patch focused on the detected target.
8. Do not invent missing files, selectors, links, IDs, components, or APIs.
9. Preserve existing navigation links and important content unless the user explicitly asks to change them.
10. For visual improvements, improve the existing structure/styles rather than replacing the page.
11. The project may use <header> as its navigation container even when no <nav> tag exists.
12. If CSS must change, create a second small exact patch for the relevant CSS rule rather than rewriting the whole stylesheet.
13. Do not claim the change works; execution and verification happen after planning.
14. If a safe targeted change cannot be designed from the supplied context, return an empty patches list.
15. Return ONLY valid JSON.

For a request like "Make the navbar better", the expected behavior is:
- inspect the existing header/navigation structure,
- preserve existing links/content,
- make a concrete targeted UX/visual improvement,
- patch only the relevant HTML/CSS blocks,
- do NOT ask the user questions,
- do NOT invent a new website.

JSON CONTRACT:
{{
  "summary": "concise description of the targeted change",
  "patches": [
    {{
      "file": "relative/path.ext",
      "old_text": "EXACT existing source text",
      "new_text": "replacement source text",
      "reason": "specific reason"
    }}
  ],
  "tests": [
    "specific validation to perform after patch"
  ]
}}
"""

        try:
            raw = self._call_ollama(
                system,
                timeout=90,
                structured_json=True,
            )
        except RuntimeError as exc:
            # Qwen/Forge can be slow on an 8 GB GPU when it has just
            # been loaded. For small targeted patch planning, fall
            # back to Velocity rather than blocking the whole engine.
            if "timed out" not in str(exc).lower():
                raise

            fallback = f"""
Return ONLY valid JSON. Plan one safe targeted patch.
REQUEST: {user_input}
TARGET: {target}
FILE: {target_file}
SOURCE:
{project_context}
Rules: preserve existing links/content; old_text must be copied exactly;
patch only the detected target; no whole-file rewrite.
Schema: {{"summary":"string","patches":[{{"file":"{target_file}","old_text":"exact source","new_text":"replacement","reason":"string"}}],"tests":[]}}
"""
            raw = self._call_ollama(
                fallback,
                timeout=75,
                structured_json=True,
                model="llama3.1:8b",
            )

        try:
            plan = self._extract_json(raw)
        except ValueError:
            retry_prompt = f"""
Return ONLY one valid JSON object.

REQUEST:
{user_input}

TARGET:
{target}

TARGET FILE:
{target_file}

SOURCE CONTEXT:
{project_context}

Rules:
- Produce a targeted patch only.
- old_text must be copied exactly from SOURCE CONTEXT.
- Preserve existing links/content.
- No whole-file rewrites.
- No invented code outside the supplied context.
- If unsafe, return an empty patches list.
- No Markdown or prose outside JSON.

JSON:
{{
  "summary": "string",
  "patches": [
    {{
      "file": "{target_file}",
      "old_text": "exact source",
      "new_text": "targeted replacement",
      "reason": "string"
    }}
  ],
  "tests": ["string"]
}}
"""
            raw = self._call_ollama(
                retry_prompt,
                timeout=120,
                structured_json=True,
            )
            plan = self._extract_json(raw)

        patches = plan.get("patches")

        if not isinstance(patches, list):
            raise ValueError(
                "Forge patch plan is missing a patches list."
            )

        plan.setdefault("summary", "")
        plan.setdefault("tests", [])

        if not isinstance(plan["tests"], list):
            plan["tests"] = []

        # Normalize patch fields and reject malformed plans early.
        normalized = []
        for patch in patches:
            if not isinstance(patch, dict):
                continue

            file_name = str(patch.get("file", "")).strip()
            old_text = str(patch.get("old_text", ""))
            new_text = str(patch.get("new_text", ""))

            if not file_name or not old_text or not new_text:
                continue

            normalized.append({
                "file": file_name,
                "old_text": old_text,
                "new_text": new_text,
                "reason": str(patch.get("reason", "")),
            })

        plan["patches"] = normalized
        return plan

    # ============================================================
    # BACKUP / SAFE PATCHING
    # ============================================================

    def _safe_project_path(
        self,
        relative_path: str,
    ) -> Optional[Path]:
        try:
            candidate = (
                self.project_root
                / Path(relative_path)
            ).resolve()

            candidate.relative_to(
                self.project_root
            )

            return candidate
        except (ValueError, OSError):
            return None

    def _create_backup(
        self,
        paths: List[Path],
    ) -> str:
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        backup_dir = self.backup_root / timestamp
        backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for path in paths:
            relative = path.relative_to(
                self.project_root
            )

            destination = backup_dir / relative
            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                path,
                destination,
            )

        return str(backup_dir)

    def _validate_patch(
        self,
        file_path: Path,
        old_text: str,
    ) -> Tuple[bool, str]:
        try:
            content = file_path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            content = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            return False, str(exc)

        count = content.count(old_text)

        if count != 1:
            return (
                False,
                f"Patch text occurs {count} times; expected exactly 1.",
            )

        return True, "Patch target verified."

    def _apply_patch(
        self,
        file_path: Path,
        old_text: str,
        new_text: str,
    ) -> bool:
        try:
            content = file_path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            content = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        if content.count(old_text) != 1:
            return False

        updated = content.replace(
            old_text,
            new_text,
            1,
        )

        if updated == content:
            return False

        file_path.write_text(
            updated,
            encoding="utf-8",
        )

        return True

    # ============================================================
    # VALIDATION
    # ============================================================

    @staticmethod
    def _validate_html(path: Path) -> Tuple[bool, str]:
        try:
            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            # Basic structural checks without requiring third-party packages.
            if "<html" not in content.lower():
                return False, "HTML document has no <html> element."

            if "<body" not in content.lower():
                return False, "HTML document has no <body> element."

            if content.count("<") < content.count(">"):
                return False, "HTML delimiter structure appears invalid."

            return True, "HTML structural validation passed."

        except OSError as exc:
            return False, str(exc)

    @staticmethod
    def _validate_css(path: Path) -> Tuple[bool, str]:
        try:
            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            if content.count("{") != content.count("}"):
                return (
                    False,
                    "CSS braces are unbalanced.",
                )

            return True, "CSS structural validation passed."

        except OSError as exc:
            return False, str(exc)

    @staticmethod
    def _validate_javascript(path: Path) -> Tuple[bool, str]:
        node = shutil.which("node")

        if not node:
            return (
                True,
                "Node.js not installed; JavaScript syntax check skipped.",
            )

        try:
            result = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, "JavaScript syntax validation passed."

            return (
                False,
                result.stderr.strip()
                or "JavaScript syntax validation failed.",
            )

        except subprocess.TimeoutExpired:
            return False, "JavaScript syntax check timed out."

        except OSError as exc:
            return False, str(exc)

    @staticmethod
    def _validate_python(path: Path) -> Tuple[bool, str]:
        try:
            py_compile.compile(
                str(path),
                doraise=True,
            )
            return True, "Python syntax validation passed."
        except py_compile.PyCompileError as exc:
            return False, str(exc)

    def validate_file(
        self,
        path: Path,
    ) -> Tuple[bool, str]:
        suffix = path.suffix.lower()

        if suffix in {".html", ".htm"}:
            return self._validate_html(path)

        if suffix in {".css", ".scss", ".sass"}:
            return self._validate_css(path)

        if suffix in {".js", ".jsx"}:
            return self._validate_javascript(path)

        if suffix == ".py":
            return self._validate_python(path)

        return True, "No specialized validator for this file type."

    # ============================================================
    # GENERIC INTELLIGENT MODIFICATION
    # ============================================================

    def modify_project(
        self,
        user_input: str,
        dry_run: bool = False,
    ) -> EditResult:
        relevant_files = self._select_relevant_files(
            user_input
        )

        if not relevant_files:
            return EditResult(
                success=False,
                message="No relevant project files were found.",
                verification="NO_TARGET_FILES",
            )

        try:
            plan = self.plan_patch(
                user_input,
                relevant_files,
            )
        except Exception as exc:
            return EditResult(
                success=False,
                message=str(exc),
                verification="PATCH_PLANNING_FAILED",
            )

        patches = plan.get("patches", [])

        if not patches:
            return EditResult(
                success=False,
                message=(
                    "Forge could not produce a safe targeted patch "
                    "from the available project context."
                ),
                verification="NO_SAFE_PATCH",
                details={"plan": plan},
            )

        resolved_patches: List[
            Tuple[Path, Dict[str, Any]]
        ] = []

        for patch in patches:
            if not isinstance(patch, dict):
                return EditResult(
                    success=False,
                    message="Invalid patch entry returned by Forge.",
                    verification="INVALID_PATCH",
                    details={"plan": plan},
                )

            relative_file = str(
                patch.get("file", "")
            ).strip()

            old_text = patch.get("old_text")
            new_text = patch.get("new_text")

            if (
                not relative_file
                or not isinstance(old_text, str)
                or not isinstance(new_text, str)
                or not old_text
            ):
                return EditResult(
                    success=False,
                    message="Patch is missing file/old_text/new_text.",
                    verification="INVALID_PATCH",
                    details={"plan": plan},
                )

            path = self._safe_project_path(
                relative_file
            )

            if not path or not path.is_file():
                return EditResult(
                    success=False,
                    message=(
                        f"Forge referenced an unavailable file: "
                        f"{relative_file}"
                    ),
                    verification="TARGET_FILE_UNAVAILABLE",
                    details={"plan": plan},
                )

            ok, message = self._validate_patch(
                path,
                old_text,
            )

            if not ok:
                return EditResult(
                    success=False,
                    file=str(path),
                    message=(
                        f"Unsafe patch for {relative_file}: "
                        f"{message}"
                    ),
                    verification="PATCH_TARGET_MISMATCH",
                    details={"plan": plan},
                )

            resolved_patches.append(
                (
                    path,
                    patch,
                )
            )

        unique_paths = list(
            dict.fromkeys(
                path
                for path, _ in resolved_patches
            )
        )

        backup = ""

        if not dry_run:
            try:
                backup = self._create_backup(
                    unique_paths
                )
            except OSError as exc:
                return EditResult(
                    success=False,
                    message=f"Backup creation failed: {exc}",
                    verification="BACKUP_FAILED",
                )

        changed_files: List[str] = []

        if dry_run:
            return EditResult(
                success=True,
                file=str(
                    unique_paths[0]
                    if unique_paths
                    else ""
                ),
                message=(
                    f"Dry-run successful. {len(resolved_patches)} "
                    "targeted patch(es) are safe to apply."
                ),
                backup="",
                changed=True,
                verification="DRY_RUN_VERIFIED",
                details={
                    "plan": plan,
                    "files": [
                        str(
                            p.relative_to(
                                self.project_root
                            )
                        )
                        for p in unique_paths
                    ],
                },
            )

        try:
            for path, patch in resolved_patches:
                changed = self._apply_patch(
                    path,
                    patch["old_text"],
                    patch["new_text"],
                )

                if not changed:
                    raise RuntimeError(
                        f"Patch was not applied to {path.name}."
                    )

                changed_files.append(
                    str(
                        path.relative_to(
                            self.project_root
                        )
                    )
                )

        except Exception as exc:
            return EditResult(
                success=False,
                message=(
                    "Patch application failed after backup creation. "
                    f"Backup: {backup}. Error: {exc}"
                ),
                backup=backup,
                changed=bool(changed_files),
                verification="PATCH_APPLICATION_FAILED",
                details={
                    "plan": plan,
                    "changed_files": changed_files,
                },
            )

        validation_results: List[str] = []

        for path in unique_paths:
            ok, message = self.validate_file(path)
            validation_results.append(
                f"{path.name}: {message}"
            )

            if not ok:
                return EditResult(
                    success=False,
                    file=str(path),
                    message=(
                        "The patch was applied, but validation failed. "
                        f"Backup: {backup}. "
                        f"Validation: {message}"
                    ),
                    backup=backup,
                    changed=True,
                    verification="VALIDATION_FAILED",
                    tests=validation_results,
                    details={
                        "plan": plan,
                        "changed_files": changed_files,
                    },
                )

        return EditResult(
            success=True,
            file=(
                str(unique_paths[0])
                if unique_paths
                else ""
            ),
            message=(
                f"Applied {len(resolved_patches)} targeted patch(es) "
                "to the existing project."
            ),
            backup=backup,
            changed=True,
            verification="PATCH_APPLIED_AND_VALIDATED",
            tests=validation_results,
            details={
                "plan": plan,
                "changed_files": changed_files,
                "requested_tests": plan.get("tests", []),
            },
        )

    # ============================================================
    # DETERMINISTIC TARGETED EDIT
    # ============================================================

    def add_create_account(
        self,
        dry_run: bool = False,
    ) -> EditResult:
        primary = self._find_primary_html()

        if not primary:
            return EditResult(
                success=False,
                message="No primary HTML file was found.",
                verification="HTML_NOT_FOUND",
            )

        try:
            content = primary.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            return EditResult(
                success=False,
                file=str(primary),
                message=f"Unable to read HTML: {exc}",
                verification="READ_FAILED",
            )

        if re.search(
            r"(create\s*account|sign\s*up|signup)",
            content,
            flags=re.IGNORECASE,
        ):
            return EditResult(
                success=True,
                file=str(primary),
                message=(
                    "The existing HTML already contains a "
                    "Create Account / Sign Up element."
                ),
                changed=False,
                verification="NO_CHANGE_NEEDED",
            )

        snippet = (
            '\n            <a href="#create-account" '
            'class="create-account">Create Account</a>\n'
        )

        # Prefer an existing nav, then header, then before body close.
        nav_match = re.search(
            r"(<nav\b[^>]*>)(.*?)(</nav>)",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if nav_match:
            insertion_point = nav_match.end(2)
            new_content = (
                content[:insertion_point]
                + snippet
                + content[insertion_point:]
            )
        else:
            header_match = re.search(
                r"(<header\b[^>]*>)(.*?)(</header>)",
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if header_match:
                insertion_point = header_match.end(2)
                new_content = (
                    content[:insertion_point]
                    + snippet
                    + content[insertion_point:]
                )
            else:
                body_close = re.search(
                    r"</body\s*>",
                    content,
                    flags=re.IGNORECASE,
                )

                if not body_close:
                    return EditResult(
                        success=False,
                        file=str(primary),
                        message=(
                            "Could not locate a safe insertion point "
                            "for Create Account."
                        ),
                        verification="NO_SAFE_INSERTION_POINT",
                    )

                insertion_point = body_close.start()
                new_content = (
                    content[:insertion_point]
                    + snippet
                    + content[insertion_point:]
                )

        if dry_run:
            return EditResult(
                success=True,
                file=str(primary),
                message=(
                    "Dry-run successful. Create Account can be "
                    "inserted into the existing HTML."
                ),
                changed=True,
                verification="DRY_RUN_VERIFIED",
            )

        try:
            backup = self._create_backup([primary])
            primary.write_text(
                new_content,
                encoding="utf-8",
            )
        except OSError as exc:
            return EditResult(
                success=False,
                file=str(primary),
                message=f"Write failed: {exc}",
                verification="WRITE_FAILED",
            )

        ok, validation = self.validate_file(primary)

        if not ok:
            return EditResult(
                success=False,
                file=str(primary),
                message=(
                    "Create Account was inserted, but validation "
                    "failed. The original file is backed up."
                ),
                backup=backup,
                changed=True,
                verification="VALIDATION_FAILED",
                tests=[validation],
            )

        return EditResult(
            success=True,
            file=str(primary),
            message="Create Account added to the existing HTML.",
            backup=backup,
            changed=True,
            verification="FILE_VERIFIED_SUCCESSFULLY",
            tests=[validation],
        )

    # ============================================================
    # HIGH-LEVEL REQUEST EXECUTION
    # ============================================================

    def execute(
        self,
        user_input: str,
        dry_run: bool = False,
    ) -> EditResult:
        analysis = self.analyze_request(
            user_input
        )

        action = analysis["action"]
        target = analysis["target"]

        if action == "inspect_and_modify" and target == "website":
            inspection = self.inspect_website()

            if not inspection.get("success"):
                return EditResult(
                    success=False,
                    message=inspection.get(
                        "message",
                        "Website inspection failed.",
                    ),
                    verification="INSPECTION_FAILED",
                    details={"analysis": analysis},
                )

            return EditResult(
                success=True,
                file=inspection["file"],
                message=(
                    f"Website inspected successfully: "
                    f"{inspection['relative_path']} "
                    f"({inspection['lines']} lines)."
                ),
                changed=False,
                verification="PROJECT_INSPECTED",
                details={
                    "analysis": analysis,
                    "inspection": inspection,
                },
            )

        if action == "modify" and target == "create_account":
            return self.add_create_account(
                dry_run=dry_run
            )

        if action == "modify":
            return self.modify_project(
                user_input,
                dry_run=dry_run,
            )

        return EditResult(
            success=False,
            message=(
                f"Request analysis produced unsupported action: "
                f"{action}"
            ),
            verification="UNSUPPORTED_ACTION",
            details={"analysis": analysis},
        )


# ================================================================
# DIRECT TEST
# ================================================================

def _print_result(label: str, result: EditResult) -> None:
    print()
    print("=" * 70)
    print(label)
    print("=" * 70)

    for key, value in asdict(result).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    print("=" * 70)
    print("ULTRON VIBE CODING ENGINE V3")
    print("=" * 70)

    engine = VibeCodingEngine()

    discovery = engine.discover_project()

    print()
    print("PROJECT")
    print("Root:", discovery.get("project_root"))
    print("Files:", discovery.get("total_files"))

    if discovery.get("success"):
        print(
            "HTML:",
            discovery["groups"]["html"],
        )
        print(
            "CSS:",
            discovery["groups"]["css"],
        )
        print(
            "JavaScript:",
            discovery["groups"]["javascript"],
        )
        print(
            "Python:",
            discovery["groups"]["python"],
        )

    primary = engine._find_primary_html()

    print()
    print("PRIMARY HTML")
    print(primary if primary else "None")

    if primary:
        inspection = engine.inspect_website()

        print()
        print("HTML INSPECTION")
        print(
            "Lines:",
            inspection.get("lines"),
        )
        print(
            "Structure:",
            inspection.get("structure"),
        )

    tests = [
        "Vibecode this website.",
        "Add Create Account to the same HTML.",
        "Make the navbar better.",
        "Fix the existing website.",
    ]

    print()
    print("REQUEST ANALYSIS")

    for test in tests:
        print()
        print(test)
        print(engine.analyze_request(test))

    print()
    print(
        "V3 build loaded successfully."
    )
