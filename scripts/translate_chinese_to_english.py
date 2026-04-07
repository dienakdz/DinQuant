#!/usr/bin/env python3
"""
Translate Chinese comments/docstrings in Python files and Chinese prose in
selected Markdown files into English.

This intentionally skips:
- generated frontend assets
- dedicated localized docs such as *_CN.md / *_CH.md / *_TW.md
- regular code string literals that are not docstrings, to avoid changing
  application behavior
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
import sys
import time
import tokenize
import urllib.parse
import urllib.request
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]
HAN_RE = re.compile(r"[\u3400-\u9FFF]")
TRANSLATE_URL = (
    "https://translate.googleapis.com/translate_a/single"
    "?client=gtx&sl=auto&tl=en&dt=t&q={query}"
)


PYTHON_GLOBS = [
    "backend_api_python/*.py",
    "backend_api_python/app/**/*.py",
    "scripts/*.py",
]

MARKDOWN_TARGETS = [
    "backend_api_python/README.md",
    "docs/FRONTEND_FAST_ANALYSIS.md",
    "docs/CHANGELOG.md",
    "docs/THIRD_PARTY_INTEGRATIONS.md",
]

SKIP_PATH_PATTERNS = [
    "/frontend/dist/",
    "/docs/README_CN.md",
    "_CN.md",
    "_CH.md",
    "_TW.md",
    "_JA.md",
    "_KO.md",
]


@dataclass(order=True)
class Replacement:
    start: int
    end: int
    text: str


def contains_han(text: str) -> bool:
    return bool(HAN_RE.search(text))


_CACHE: dict[str, str] = {}


def translate_text(text: str) -> str:
    text = text.strip("\n")
    if not text or not contains_han(text):
        return text
    if text in _CACHE:
        return _CACHE[text]

    url = TRANSLATE_URL.format(query=urllib.parse.quote(text))
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            translated = "".join(part[0] for part in payload[0] if part and part[0])
            translated = normalize_translation(translated)
            _CACHE[text] = translated
            return translated
        except Exception as exc:  # pragma: no cover - best effort script
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Translation failed for text: {text!r}") from last_error


def normalize_translation(text: str) -> str:
    text = text.replace("K line", "K-line")
    text = text.replace("K Line", "K-line")
    text = text.replace("candlestick line", "candlestick")
    text = text.replace("real-time market", "realtime market")
    text = text.replace("real-time quote", "realtime quote")
    return text


def line_start_offsets(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def to_offset(line_starts: list[int], lineno: int, col: int) -> int:
    return line_starts[lineno - 1] + col


def translate_preserving_indent(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        body = line.rstrip("\r\n")
        newline = line[len(body):]
        if not contains_han(body):
            out.append(line)
            continue
        leading = re.match(r"\s*", body).group(0)
        translated = translate_text(body[len(leading):])
        out.append(f"{leading}{translated}{newline}")
    return "".join(out)


DOCSTRING_ONE_LINE_RE = re.compile(
    r'^(?P<indent>\s*)(?P<prefix>[rubfRUBF]*)(?P<quote>"""|\'\'\')(?P<body>.*?)(?P=quote)(?P<trailing>\s*(?:#.*)?)$'
)
DOCSTRING_START_RE = re.compile(
    r'^(?P<indent>\s*)(?P<prefix>[rubfRUBF]*)(?P<quote>"""|\'\'\')(?P<body>.*)$'
)


def translate_python_file(path: pathlib.Path) -> bool:
    src = path.read_text(encoding="utf-8")
    docstring_translated = translate_python_docstrings(src)
    line_starts = line_start_offsets(docstring_translated)
    replacements: list[Replacement] = []

    for token in tokenize.generate_tokens(io.StringIO(docstring_translated).readline):
        if token.type != tokenize.COMMENT or not contains_han(token.string):
            continue
        leading = re.match(r"#\s*", token.string).group(0)
        translated = translate_text(token.string[len(leading):])
        replacement = f"{leading}{translated}"
        replacements.append(
            Replacement(
                start=to_offset(line_starts, token.start[0], token.start[1]),
                end=to_offset(line_starts, token.end[0], token.end[1]),
                text=replacement,
            )
        )

    if not replacements and docstring_translated == src:
        return False

    new_src = apply_replacements(docstring_translated, replacements)
    if new_src != src:
        path.write_text(new_src, encoding="utf-8")
        return True
    return False


def translate_python_docstrings(src: str) -> str:
    lines = src.splitlines(keepends=True)
    out: list[str] = []
    in_docstring = False
    active_quote = ""

    for line in lines:
        stripped = line.lstrip()
        if not in_docstring:
            one_line = DOCSTRING_ONE_LINE_RE.match(line.rstrip("\n"))
            if one_line and stripped.startswith(one_line.group("prefix") + one_line.group("quote")):
                body = one_line.group("body")
                if contains_han(body):
                    body = translate_text(body)
                newline = "\n" if line.endswith("\n") else ""
                out.append(
                    f"{one_line.group('indent')}{one_line.group('prefix')}{one_line.group('quote')}"
                    f"{body}{one_line.group('quote')}{one_line.group('trailing')}{newline}"
                )
                continue

            start = DOCSTRING_START_RE.match(line.rstrip("\n"))
            if start and stripped.startswith(start.group("prefix") + start.group("quote")):
                in_docstring = True
                active_quote = start.group("quote")
                body = start.group("body")
                if contains_han(body):
                    body = translate_text(body)
                newline = "\n" if line.endswith("\n") else ""
                out.append(
                    f"{start.group('indent')}{start.group('prefix')}{start.group('quote')}{body}{newline}"
                )
                continue

            out.append(line)
            continue

        line_no_newline = line.rstrip("\n")
        if active_quote in line_no_newline:
            before, after = line_no_newline.split(active_quote, 1)
            if contains_han(before):
                before = translate_preserving_indent(before).rstrip("\n")
            out.append(f"{before}{active_quote}{after}{'\n' if line.endswith('\n') else ''}")
            in_docstring = False
            active_quote = ""
        else:
            out.append(translate_preserving_indent(line))

    return "".join(out)


def translate_markdown_file(path: pathlib.Path) -> bool:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    out: list[str] = []
    in_fence = False
    changed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or not contains_han(line):
            out.append(line)
            continue
        translated = translate_preserving_indent(line)
        out.append(translated)
        changed = changed or translated != line

    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed


def apply_replacements(text: str, replacements: list[Replacement]) -> str:
    dedup: list[Replacement] = []
    seen: set[tuple[int, int]] = set()
    for item in sorted(replacements, reverse=True):
        key = (item.start, item.end)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    for item in dedup:
        text = text[: item.start] + item.text + text[item.end :]
    return text


def should_skip(path: pathlib.Path) -> bool:
    posix = path.as_posix()
    return any(pattern in posix for pattern in SKIP_PATH_PATTERNS)


def iter_python_targets() -> list[pathlib.Path]:
    paths: set[pathlib.Path] = set()
    for pattern in PYTHON_GLOBS:
        paths.update(ROOT.glob(pattern))
    return sorted(path for path in paths if path.is_file() and not should_skip(path))


def iter_markdown_targets() -> list[pathlib.Path]:
    return [ROOT / target for target in MARKDOWN_TARGETS if (ROOT / target).exists()]


def resolve_targets(args: argparse.Namespace) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    if args.paths:
        python_files: list[pathlib.Path] = []
        markdown_files: list[pathlib.Path] = []
        for raw in args.paths:
            path = (ROOT / raw).resolve() if not pathlib.Path(raw).is_absolute() else pathlib.Path(raw)
            if not path.exists():
                continue
            if path.suffix == ".py":
                python_files.append(path)
            elif path.suffix == ".md":
                markdown_files.append(path)
        return python_files, markdown_files
    return iter_python_targets(), iter_markdown_targets()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    python_targets, markdown_targets = resolve_targets(args)
    changed_files: list[str] = []

    for path in python_targets:
        if args.verbose:
            print(f"[py] {path.relative_to(ROOT).as_posix()}", file=sys.stderr)
        if translate_python_file(path):
            changed_files.append(path.relative_to(ROOT).as_posix())

    for path in markdown_targets:
        if args.verbose:
            print(f"[md] {path.relative_to(ROOT).as_posix()}", file=sys.stderr)
        if translate_markdown_file(path):
            changed_files.append(path.relative_to(ROOT).as_posix())

    for relpath in changed_files:
        print(relpath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
