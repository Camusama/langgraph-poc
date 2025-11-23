"""Utilities to load mock assets for the POC."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Optional


ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def parse_date_from_name(name: str) -> Optional[str]:
    """Extract YYYY-MM-DD from filename prefix if present."""
    if len(name) < 10:
        return None
    prefix = name[:10]
    if prefix[4] == "-" and prefix[7] == "-":
        return prefix
    return None


def load_assets_upto(date_str: str) -> List[Dict[str, str]]:
    """Return assets with date <= date_str sorted by name."""
    files: List[Dict[str, str]] = []
    if not ASSETS_DIR.exists():
        return files

    for path in ASSETS_DIR.glob("*.md"):
        name = path.name
        parsed = parse_date_from_name(name)
        if not parsed:
            continue
        if parsed <= date_str:
            content = path.read_text(encoding="utf-8", errors="ignore")
            files.append({"name": name, "date": parsed, "content": content})
    files.sort(key=lambda x: x["name"])
    return files


def load_assets_by_date(date_str: str) -> List[Dict[str, str]]:
    """Return assets exactly matching the date prefix."""
    if not ASSETS_DIR.exists():
        return []
    files: List[Dict[str, str]] = []
    for path in ASSETS_DIR.glob(f"{date_str}*.md"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        files.append({"name": path.name, "date": date_str, "content": content})
    files.sort(key=lambda x: x["name"])
    return files


def load_members_file() -> List[str]:
    """Read member emails from members.md if present."""
    members_path = ASSETS_DIR / "members.md"
    if not members_path.exists():
        return []
    lines = members_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [line.strip() for line in lines if line.strip()]
