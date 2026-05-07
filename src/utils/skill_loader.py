"""
Skill loader — picks relevant skill cards from src/skills/ based on a topic's
keywords/cluster/industry, and returns concatenated markdown for injection
into agent prompts.

Each .md file in src/skills/{equipment,industries,frameworks}/ is a
self-contained reference card. Filenames are dash-separated keywords
(e.g. `automotive-oem.md`, `compressor.md`). Score = how many of the topic's
search terms match the filename.

Files are read fresh per call (cheap; small markdown). Cap at top-N
matches to keep prompts manageable.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills"
HEADER = "\n--- SKILL CARDS (reference only — do not quote literally) ---\n"


def _score(filename: str, terms: set[str]) -> int:
    """Count how many of `terms` appear in the filename's words."""
    name_words = filename.lower().replace(".md", "").replace("-", " ").split()
    score = 0
    for word in name_words:
        for t in terms:
            if not t:
                continue
            if word in t or t in word:
                score += 1
                break
    return score


def _terms_from_topic(topic: dict) -> set[str]:
    raw: list[str] = []
    if "keywords" in topic and topic["keywords"]:
        raw.extend(topic["keywords"])
    for key in ("cluster", "industry", "topic"):
        v = topic.get(key)
        if v:
            raw.append(str(v))
    # Normalize: lowercase, strip, drop empty
    return {s.strip().lower() for s in raw if s and str(s).strip()}


def load_skills(topic: dict, max_cards: int = 3) -> str:
    """Return concatenated markdown of the top-N most relevant skill cards.
    Returns empty string if no matches (or skills/ directory is missing)."""
    if not SKILLS_DIR.exists():
        return ""
    terms = _terms_from_topic(topic)
    if not terms:
        return ""

    scored: list[tuple[int, Path]] = []
    for f in SKILLS_DIR.rglob("*.md"):
        s = _score(f.name, terms)
        if s > 0:
            scored.append((s, f))
    if not scored:
        return ""

    # Sort by score desc, then path for deterministic ordering
    scored.sort(key=lambda x: (-x[0], str(x[1])))
    selected = scored[:max_cards]

    parts = [HEADER]
    for _, sf in selected:
        parts.append(sf.read_text(encoding="utf-8"))
    logger.info(f"📇 Loaded {len(selected)} skill card(s): "
                f"{[p.stem for _, p in selected]}")
    return "\n\n".join(parts)
