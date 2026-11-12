from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RELEASES_URL = "https://github.com/is90057/BaiZe/releases"
RELEASES_LATEST_URL = "https://github.com/is90057/BaiZe/releases/latest"
API_LATEST_RELEASE_URL = "https://api.github.com/repos/is90057/BaiZe/releases/latest"
API_RELEASES_URL = "https://api.github.com/repos/is90057/BaiZe/releases"
API_TAGS_URL = "https://api.github.com/repos/is90057/BaiZe/tags"

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class UpdateCheckResult:
    current_version: str
    latest_version: str = ""
    has_update: bool = False
    release_url: str = RELEASES_URL
    release_name: str = ""
    release_notes: str = ""
    published_at: str = ""
    error: str = ""


def parse_version_tuple(tag: str) -> tuple[tuple[int, ...], int]:
    """Parse a version tag like 'v1.0.1' or '1.2.0-beta.1' into a comparable tuple.
    Returns (numeric_parts, is_final_release_flag)."""
    cleaned = (tag or "").strip().lstrip("vV")
    if not cleaned:
        return ((0,), 0)
    main_part, *pre_parts = re.split(r"[-+]", cleaned, maxsplit=1)
    nums: list[int] = []
    for piece in main_part.split("."):
        m = re.match(r"^(\d+)", piece.strip())
        nums.append(int(m.group(1)) if m else 0)
    while len(nums) > 1 and nums[-1] == 0:
        nums.pop()
    is_final = 0 if pre_parts else 1
    return (tuple(nums or [0]), is_final)


def is_newer_version(latest_tag: str, current_tag: str) -> bool:
    """Return True if `latest_tag` is strictly newer than `current_tag`."""
    if not latest_tag or not current_tag:
        return False
    if latest_tag.strip() == current_tag.strip():
        return False
    return parse_version_tuple(latest_tag) > parse_version_tuple(current_tag)


def get_current_version(repo_dir: Path | None = None) -> str:
    """Retrieve the current version from the local Git tag (e.g. 'v1.0.1')."""
    root = repo_dir or REPO_ROOT

    # 1. Try `git describe --tags --abbrev=0` (nearest ancestor tag on current branch)
    try:
        proc = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass

    # 2. Try `git tag --sort=-v:refname` (highest version tag in repo)
    try:
        proc = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first_line = proc.stdout.strip().splitlines()[0].strip()
            if first_line:
                return first_line
    except Exception:
        pass

    # 3. Fallback: read .git/refs/tags or .git/packed-refs directly if git binary is missing
    try:
        git_dir = root / ".git"
        candidates: list[str] = []
        tags_dir = git_dir / "refs" / "tags"
        if tags_dir.is_dir():
            for p in tags_dir.rglob("*"):
                if p.is_file():
                    candidates.append(p.relative_to(tags_dir).as_posix())
        packed = git_dir / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "refs/tags/" in line and not line.startswith("#") and "^" not in line:
                    candidates.append(line.split("refs/tags/", 1)[1].strip())
        if candidates:
            candidates.sort(key=parse_version_tuple, reverse=True)
            return candidates[0]
    except Exception:
        pass

    return "v1.0.0"


def _http_get_text(url: str, accept: str = "text/html,application/xhtml+xml,application/json", timeout: float = 8.0) -> tuple[str, str]:
    """Perform an HTTP GET request and return (response_text, final_url)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BaiZe-Updater/1.0 (https://github.com/is90057/BaiZe)",
            "Accept": accept,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl() or url
        raw = resp.read()
        return raw.decode("utf-8", errors="replace"), final_url


def check_github_updates(current_version: str | None = None, timeout: float = 8.0) -> UpdateCheckResult:
    """Check https://github.com/is90057/BaiZe/releases for the latest version tag."""
    cur_ver = current_version or get_current_version()
    result = UpdateCheckResult(current_version=cur_ver, release_url=RELEASES_URL)
    last_err = ""

    # Strategy 1: Check https://github.com/is90057/BaiZe/releases/latest redirect
    try:
        html_latest, final_url = _http_get_text(RELEASES_LATEST_URL, timeout=timeout)
        m = re.search(r"/is90057/BaiZe/releases/tag/([^/?#\"'<>\s]+)", final_url)
        if not m:
            m = re.search(r"/is90057/BaiZe/releases/tag/([^/?#\"'<>\s]+)", html_latest)
        if m:
            tag = urllib.parse.unquote(m.group(1)).strip()
            result.latest_version = tag
            result.release_url = f"{RELEASES_URL}/tag/{tag}"
            result.has_update = is_newer_version(tag, cur_ver)
    except Exception as exc:
        last_err = str(exc)

    # Strategy 2: Check https://github.com/is90057/BaiZe/releases HTML page directly
    if not result.latest_version:
        try:
            html_rel, _ = _http_get_text(RELEASES_URL, timeout=timeout)
            tags = re.findall(r"/is90057/BaiZe/releases/tag/([^/?#\"'<>\s]+)", html_rel)
            if not tags:
                tags = re.findall(r"/is90057/BaiZe/tree/(v\d+[^/?#\"'<>\s]*)", html_rel)
            if tags:
                clean_tags = [urllib.parse.unquote(t).strip() for t in tags if t.strip()]
                clean_tags.sort(key=parse_version_tuple, reverse=True)
                best_tag = clean_tags[0]
                result.latest_version = best_tag
                result.release_url = f"{RELEASES_URL}/tag/{best_tag}"
                result.has_update = is_newer_version(best_tag, cur_ver)
        except Exception as exc:
            last_err = str(exc)

    # Strategy 3: Enrich or fallback via GitHub REST API (releases/latest, releases, tags)
    try:
        raw_json, _ = _http_get_text(
            API_LATEST_RELEASE_URL,
            accept="application/vnd.github+json",
            timeout=timeout,
        )
        data = json.loads(raw_json)
        api_tag = str(data.get("tag_name") or "").strip()
        if api_tag:
            if not result.latest_version or is_newer_version(api_tag, result.latest_version):
                result.latest_version = api_tag
            result.release_url = str(data.get("html_url") or f"{RELEASES_URL}/tag/{api_tag}")
            result.release_name = str(data.get("name") or api_tag)
            result.release_notes = str(data.get("body") or "").strip()
            result.published_at = str(data.get("published_at") or "")[:10]
            result.has_update = is_newer_version(result.latest_version, cur_ver)
            return result
    except Exception as exc:
        if not last_err:
            last_err = str(exc)

    if not result.latest_version:
        try:
            raw_json, _ = _http_get_text(
                API_RELEASES_URL,
                accept="application/vnd.github+json",
                timeout=timeout,
            )
            rel_list = json.loads(raw_json)
            if isinstance(rel_list, list) and rel_list:
                rel_list_valid = [r for r in rel_list if isinstance(r, dict) and r.get("tag_name") and not r.get("draft")]
                if rel_list_valid:
                    rel_list_valid.sort(key=lambda r: parse_version_tuple(str(r.get("tag_name", ""))), reverse=True)
                    top = rel_list_valid[0]
                    api_tag = str(top.get("tag_name") or "").strip()
                    result.latest_version = api_tag
                    result.release_url = str(top.get("html_url") or f"{RELEASES_URL}/tag/{api_tag}")
                    result.release_name = str(top.get("name") or api_tag)
                    result.release_notes = str(top.get("body") or "").strip()
                    result.published_at = str(top.get("published_at") or "")[:10]
                    result.has_update = is_newer_version(api_tag, cur_ver)
                    return result
        except Exception as exc:
            last_err = str(exc)

    if not result.latest_version:
        try:
            raw_json, _ = _http_get_text(
                API_TAGS_URL,
                accept="application/vnd.github+json",
                timeout=timeout,
            )
            tag_list = json.loads(raw_json)
            if isinstance(tag_list, list) and tag_list:
                tag_names = [str(t.get("name") or "").strip() for t in tag_list if isinstance(t, dict) and t.get("name")]
                if tag_names:
                    tag_names.sort(key=parse_version_tuple, reverse=True)
                    best_tag = tag_names[0]
                    result.latest_version = best_tag
                    result.release_url = f"{RELEASES_URL}/tag/{best_tag}"
                    result.has_update = is_newer_version(best_tag, cur_ver)
                    return result
        except Exception as exc:
            last_err = str(exc)

    if not result.latest_version and last_err:
        result.error = last_err

    return result

