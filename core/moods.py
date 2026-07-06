from __future__ import annotations

"""Deterministic mood taxonomy and explainable scoring helpers."""

from dataclasses import dataclass
import json
import re
from typing import Iterable, Mapping, Sequence

from core.genres import split_and_normalize

DEFAULT_MAX_MOODS = 3
DEFAULT_MIN_SCORE = 4

MOOD_TAXONOMY: dict[str, dict[str, str]] = {
    "Scary": {
        "description": "Fear, dread, menace, monsters, or haunted tension.",
    },
    "Funny": {
        "description": "Comedic, witty, playful, or absurd.",
    },
    "Light": {
        "description": "Easygoing, low-friction, and not emotionally heavy.",
    },
    "Intense": {
        "description": "High-stakes, violent, suspenseful, or emotionally forceful.",
    },
    "Cozy": {
        "description": "Comforting, warm, gentle, or familiar.",
    },
    "Romantic": {
        "description": "Love, dating, longing, or relationship-forward stories.",
    },
    "Family": {
        "description": "Family-friendly, animated, young-audience, or all-ages stories.",
    },
    "Mind-bending": {
        "description": "Reality-bending, cerebral, twisty, surreal, or puzzle-box stories.",
    },
    "Atmospheric": {
        "description": "Moody, immersive, eerie, stylish, or place-driven.",
    },
    "Gritty": {
        "description": "Hard-edged, raw, criminal, violent, or grounded.",
    },
    "High-energy": {
        "description": "Fast, kinetic, adventurous, explosive, or action-forward.",
    },
    "Thoughtful": {
        "description": "Reflective, thematic, character-driven, or serious.",
    },
    "Epic": {
        "description": "Large-scale, sweeping, historic, mythic, or grand.",
    },
    "Bleak": {
        "description": "Dark, tragic, punishing, hopeless, or emotionally heavy.",
    },
}

NEGATIVE_MOOD_TAXONOMY: dict[str, dict[str, str]] = {
    "not_scary": {"description": "Avoid fear, horror, dread, and jump-scare material."},
    "not_bleak": {"description": "Avoid punishing, hopeless, or tragic movies."},
    "not_intense": {"description": "Avoid violent, suspense-heavy, or high-stress movies."},
    "not_long": {"description": "Avoid long runtimes."},
    "not_slow": {"description": "Avoid quiet, slow, or heavily reflective movies."},
    "not_family": {"description": "Avoid family/kid-forward movies."},
    "not_romantic": {"description": "Avoid romance-forward movies."},
}


@dataclass(frozen=True)
class MoodEvidence:
    mood: str
    source: str
    signal: str
    weight: int

    def label(self) -> str:
        return f"{self.source}:{self.signal}+{self.weight}"


@dataclass(frozen=True)
class MoodScore:
    mood: str
    score: int
    evidence: tuple[MoodEvidence, ...]

    @property
    def confidence(self) -> str:
        if self.score >= 8:
            return "high"
        if self.score >= DEFAULT_MIN_SCORE:
            return "medium"
        return "low"

    @property
    def explanation(self) -> str:
        return "; ".join(item.label() for item in self.evidence)


@dataclass(frozen=True)
class MoodAnalysis:
    selected: tuple[MoodScore, ...]
    candidates: tuple[MoodScore, ...]
    avoidance_flags: tuple[str, ...]

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(item.mood for item in self.selected)


@dataclass(frozen=True)
class MoodRule:
    genre_strong: frozenset[str] = frozenset()
    genre_soft: frozenset[str] = frozenset()
    keyword_strong: frozenset[str] = frozenset()
    keyword_soft: frozenset[str] = frozenset()
    plot_strong: tuple[str, ...] = ()
    plot_soft: tuple[str, ...] = ()
    certificates: frozenset[str] = frozenset()
    runtime_max: int | None = None
    runtime_min: int | None = None


MOOD_RULES: dict[str, MoodRule] = {
    "Scary": MoodRule(
        genre_strong=frozenset({"horror"}),
        genre_soft=frozenset({"thriller", "mystery"}),
        keyword_strong=frozenset(
            {
                "ghost",
                "haunting",
                "haunted house",
                "monster",
                "possession",
                "serial killer",
                "slasher",
                "supernatural",
                "vampire",
                "zombie",
            }
        ),
        keyword_soft=frozenset({"blood", "creature", "curse", "nightmare", "survival"}),
        plot_strong=("haunted", "killer", "possession", "supernatural"),
        plot_soft=("terrifying", "terror", "mysterious deaths", "nightmare"),
    ),
    "Funny": MoodRule(
        genre_strong=frozenset({"comedy"}),
        keyword_strong=frozenset({"stand-up comedy", "satire", "parody", "spoof"}),
        keyword_soft=frozenset({"buddy comedy", "mistaken identity", "wedding"}),
        plot_strong=("hilarious", "comedy", "comedian"),
        plot_soft=("wacky", "absurd", "misadventures", "hijinks"),
    ),
    "Light": MoodRule(
        genre_soft=frozenset({"comedy", "family", "animation", "music"}),
        keyword_strong=frozenset({"feel-good", "holiday", "road trip"}),
        keyword_soft=frozenset({"friendship", "school", "vacation"}),
        plot_strong=("feel-good", "lighthearted"),
        plot_soft=("learns a lesson", "new friend", "adventure begins"),
        certificates=frozenset({"g", "pg"}),
        runtime_max=105,
    ),
    "Intense": MoodRule(
        genre_strong=frozenset({"thriller", "war"}),
        genre_soft=frozenset({"action", "crime", "horror"}),
        keyword_strong=frozenset({"assassin", "kidnapping", "revenge", "terrorism"}),
        keyword_soft=frozenset({"battle", "chase", "conspiracy", "murder", "survival"}),
        plot_strong=("must survive", "race against time", "deadly"),
        plot_soft=("dangerous", "violent", "threatens"),
        certificates=frozenset({"r", "nc-17"}),
    ),
    "Cozy": MoodRule(
        genre_soft=frozenset({"family", "animation", "romance", "comedy"}),
        keyword_strong=frozenset({"christmas", "holiday", "small town"}),
        keyword_soft=frozenset({"friendship", "home", "neighbor", "reunion"}),
        plot_strong=("small town", "holiday", "home for"),
        plot_soft=("family gathers", "old friend", "warm"),
        certificates=frozenset({"g", "pg"}),
        runtime_max=115,
    ),
    "Romantic": MoodRule(
        genre_strong=frozenset({"romance"}),
        genre_soft=frozenset({"comedy", "drama"}),
        keyword_strong=frozenset({"falling in love", "love triangle", "romantic comedy"}),
        keyword_soft=frozenset({"dating", "marriage", "wedding"}),
        plot_strong=("falls in love", "fall in love", "love affair"),
        plot_soft=("romance", "relationship", "wedding"),
    ),
    "Family": MoodRule(
        genre_strong=frozenset({"family", "animation"}),
        keyword_strong=frozenset({"children", "coming of age", "friendship", "toy"}),
        keyword_soft=frozenset({"animal", "school", "teenager"}),
        plot_strong=("family", "young", "child"),
        plot_soft=("friendship", "children", "parents"),
        certificates=frozenset({"g", "pg"}),
    ),
    "Mind-bending": MoodRule(
        genre_soft=frozenset({"science fiction", "mystery", "fantasy"}),
        keyword_strong=frozenset(
            {
                "alternate reality",
                "dream",
                "memory",
                "mind control",
                "parallel universe",
                "surrealism",
                "time loop",
                "time travel",
            }
        ),
        keyword_soft=frozenset(
            {"afterlife", "experiment", "illusion", "simulation", "space opera"}
        ),
        plot_strong=("alternate reality", "time loop", "time travel", "simulation"),
        plot_soft=("dream", "memory", "reality", "mysterious"),
    ),
    "Atmospheric": MoodRule(
        genre_soft=frozenset({"mystery", "thriller", "horror", "fantasy", "science fiction"}),
        keyword_strong=frozenset({"neo-noir", "noir", "isolation", "rain", "small town"}),
        keyword_soft=frozenset({"detective", "fog", "haunted house", "secret", "winter"}),
        plot_strong=("isolated", "eerie", "mysterious town"),
        plot_soft=("dark secret", "remote", "strange"),
    ),
    "Gritty": MoodRule(
        genre_strong=frozenset({"crime", "western"}),
        genre_soft=frozenset({"drama", "thriller", "war"}),
        keyword_strong=frozenset({"gang", "mafia", "prison", "street gang"}),
        keyword_soft=frozenset({"corruption", "drug", "police", "revenge"}),
        plot_strong=("criminal underworld", "corrupt", "gang"),
        plot_soft=("crime", "police", "violence"),
        certificates=frozenset({"r", "nc-17"}),
    ),
    "High-energy": MoodRule(
        genre_strong=frozenset({"action", "adventure"}),
        genre_soft=frozenset({"science fiction", "war"}),
        keyword_strong=frozenset({"car chase", "martial arts", "superhero"}),
        keyword_soft=frozenset({"battle", "chase", "explosion", "rescue"}),
        plot_strong=("must stop", "mission", "save the world"),
        plot_soft=("adventure", "battle", "chase"),
        runtime_max=140,
    ),
    "Thoughtful": MoodRule(
        genre_strong=frozenset({"documentary", "history"}),
        genre_soft=frozenset({"drama", "science fiction", "mystery"}),
        keyword_strong=frozenset({"biography", "existentialism", "philosophy"}),
        keyword_soft=frozenset({"grief", "memory", "politics", "social issues"}),
        plot_strong=("reflects on", "questions", "struggles with"),
        plot_soft=("life", "meaning", "truth", "past"),
    ),
    "Epic": MoodRule(
        genre_strong=frozenset({"adventure", "war", "fantasy", "history"}),
        keyword_strong=frozenset({"empire", "kingdom", "quest", "space opera", "war"}),
        keyword_soft=frozenset({"battle", "journey", "legend", "mythology"}),
        plot_strong=("epic", "kingdom", "war"),
        plot_soft=("journey", "quest", "against an empire"),
        runtime_min=135,
    ),
    "Bleak": MoodRule(
        genre_soft=frozenset({"drama", "horror", "war", "crime"}),
        keyword_strong=frozenset({"apocalypse", "dystopia", "tragedy"}),
        keyword_soft=frozenset({"death", "grief", "loss", "suicide"}),
        plot_strong=("hopeless", "devastated", "tragic"),
        plot_soft=("grief", "loss", "death", "desperate"),
        certificates=frozenset({"r", "nc-17"}),
    ),
}

MOOD_ALIASES: dict[str, str] = {
    "dark": "Bleak",
    "dreamy": "Atmospheric",
    "exciting": "High-energy",
    "heartfelt": "Cozy",
    "high-octane": "High-energy",
    "intimate": "Thoughtful",
    "moody": "Atmospheric",
    "uplifting": "Light",
}

NEGATIVE_MOOD_FLAGS: dict[str, frozenset[str]] = {
    "not_scary": frozenset({"Scary"}),
    "not_bleak": frozenset({"Bleak"}),
    "not_intense": frozenset({"Intense", "Gritty"}),
    "not_long": frozenset({"Epic"}),
    "not_slow": frozenset({"Thoughtful", "Atmospheric"}),
    "not_family": frozenset({"Family"}),
    "not_romantic": frozenset({"Romantic"}),
}


def _normalize_genres(raw: Iterable[str]) -> list[str]:
    return [label.lower() for label in split_and_normalize(raw)]


def _flatten_keywords(raw: object | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = re.split(r"[;,]", value)
        else:
            return _flatten_keywords(parsed)
        return [item.strip() for item in parsed if item.strip()]
    if isinstance(raw, Mapping):
        values: list[str] = []
        for value in raw.values():
            values.extend(_flatten_keywords(value))
        return values
    if isinstance(raw, Sequence):
        values = []
        for item in raw:
            values.extend(_flatten_keywords(item))
        return values
    return [str(raw).strip()] if str(raw).strip() else []


def _normalize_keyword(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " ").replace("-", " "))


def _plot_matches(plot: str, phrase: str) -> bool:
    cleaned_phrase = re.escape(_normalize_keyword(phrase))
    return re.search(rf"(?<![a-z0-9]){cleaned_phrase}(?![a-z0-9])", plot) is not None


def _add(
    evidence: dict[str, list[MoodEvidence]],
    mood: str,
    *,
    source: str,
    signal: str,
    weight: int,
) -> None:
    evidence.setdefault(mood, []).append(
        MoodEvidence(mood=mood, source=source, signal=signal, weight=weight)
    )


def analyze_moods(
    genres: Iterable[str],
    *,
    keywords: object | None = None,
    plot: str | None = None,
    certificate: str | None = None,
    runtime: int | None = None,
    max_moods: int = DEFAULT_MAX_MOODS,
    min_score: int = DEFAULT_MIN_SCORE,
) -> MoodAnalysis:
    """Return selected moods plus scored evidence for every candidate mood."""

    genre_tokens = set(_normalize_genres(genres))
    keyword_tokens = {_normalize_keyword(value) for value in _flatten_keywords(keywords)}
    plot_text = _normalize_keyword(plot or "")
    certificate_token = (certificate or "").strip().lower()
    evidence: dict[str, list[MoodEvidence]] = {}

    for mood, rule in MOOD_RULES.items():
        for token in sorted(genre_tokens & rule.genre_strong):
            _add(evidence, mood, source="genre", signal=token, weight=3)
        for token in sorted(genre_tokens & rule.genre_soft):
            _add(evidence, mood, source="genre", signal=token, weight=1)
        for token in sorted(keyword_tokens & rule.keyword_strong):
            _add(evidence, mood, source="keyword", signal=token, weight=4)
        for token in sorted(keyword_tokens & rule.keyword_soft):
            _add(evidence, mood, source="keyword", signal=token, weight=2)
        for phrase in rule.plot_strong:
            if _plot_matches(plot_text, phrase):
                _add(evidence, mood, source="plot", signal=phrase, weight=3)
        for phrase in rule.plot_soft:
            if _plot_matches(plot_text, phrase):
                _add(evidence, mood, source="plot", signal=phrase, weight=1)
        if certificate_token and certificate_token in rule.certificates:
            _add(evidence, mood, source="certificate", signal=certificate_token.upper(), weight=1)
        if rule.runtime_max is not None and runtime is not None and runtime <= rule.runtime_max:
            _add(evidence, mood, source="runtime", signal=f"<={rule.runtime_max}", weight=1)
        if rule.runtime_min is not None and runtime is not None and runtime >= rule.runtime_min:
            _add(evidence, mood, source="runtime", signal=f">={rule.runtime_min}", weight=1)

    candidates = tuple(
        sorted(
            (
                MoodScore(
                    mood=mood,
                    score=sum(item.weight for item in items),
                    evidence=tuple(items),
                )
                for mood, items in evidence.items()
            ),
            key=lambda item: (-item.score, item.mood),
        )
    )
    selected = tuple(item for item in candidates if item.score >= min_score)[:max_moods]
    selected_names = {item.mood for item in selected}
    avoidance = tuple(
        flag
        for flag, disallowed in NEGATIVE_MOOD_FLAGS.items()
        if selected_names.intersection(disallowed)
        or (flag == "not_long" and runtime is not None and runtime >= 135)
    )
    return MoodAnalysis(selected=selected, candidates=candidates, avoidance_flags=avoidance)


def normalize_mood_labels(raw: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    by_lower = {name.lower(): name for name in MOOD_TAXONOMY}
    for value in raw:
        label = str(value).strip()
        if not label:
            continue
        canonical = by_lower.get(label.lower()) or MOOD_ALIASES.get(label.lower())
        if canonical and canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return tuple(normalized)


def score_moods(
    genres: Iterable[str],
    *,
    keywords: object | None = None,
    plot: str | None = None,
    certificate: str | None = None,
    runtime: int | None = None,
    max_moods: int = DEFAULT_MAX_MOODS,
    min_score: int = DEFAULT_MIN_SCORE,
) -> list[str]:
    analysis = analyze_moods(
        genres,
        keywords=keywords,
        plot=plot,
        certificate=certificate,
        runtime=runtime,
        max_moods=max_moods,
        min_score=min_score,
    )
    return list(analysis.labels)


def avoidance_flags_for_moods(
    moods: Iterable[str], *, runtime: int | None = None
) -> tuple[str, ...]:
    labels = set(normalize_mood_labels(moods))
    flags = [
        flag
        for flag, disallowed in NEGATIVE_MOOD_FLAGS.items()
        if labels.intersection(disallowed)
        or (flag == "not_long" and runtime is not None and runtime >= 135)
    ]
    return tuple(flags)


__all__ = [
    "DEFAULT_MAX_MOODS",
    "DEFAULT_MIN_SCORE",
    "MOOD_ALIASES",
    "MOOD_RULES",
    "MOOD_TAXONOMY",
    "NEGATIVE_MOOD_FLAGS",
    "NEGATIVE_MOOD_TAXONOMY",
    "MoodAnalysis",
    "MoodEvidence",
    "MoodScore",
    "analyze_moods",
    "avoidance_flags_for_moods",
    "normalize_mood_labels",
    "score_moods",
]
