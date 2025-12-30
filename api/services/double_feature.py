from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from random import Random
from typing import Optional, Tuple

from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.models.movie import Genre, Mood, Movie
from api.models.person import Role, RoleType
from api.services.flic_ordering import fetch_movies_in_rank_order, rank_movie_ids_by_flic
from core.picker import PickerCandidate, PickerFilters, calculate_flic_score

DEFAULT_DOUBLE_FEATURE_RUNTIME = 240


@dataclass(frozen=True)
class DoubleFeatureSelection:
    primary: Movie
    secondary: Movie
    runtime_cap: int
    total_runtime: str
    theme_label: Optional[str] = None


def _movie_genres(movie: Movie) -> list[str]:
    return [genre.name for genre in getattr(movie, "genres", []) if genre.name]


def _movie_moods(movie: Movie) -> list[str]:
    return [mood.name for mood in getattr(movie, "moods", []) if mood.name]


def _movie_directors(movie: Movie) -> list[str]:
    directors: list[str] = []
    for role in getattr(movie, "roles", []):
        if role.role_type == RoleType.DIRECTOR and role.person and role.person.name:
            if role.person.name not in directors:
                directors.append(role.person.name)
    return directors


def _movie_leads(movie: Movie, *, limit: int = 2) -> list[str]:
    actors = [
        role
        for role in getattr(movie, "roles", [])
        if role.role_type == RoleType.ACTOR and role.person and role.person.name
    ]
    actors.sort(
        key=lambda role: (
            role.billing_order is None,
            role.billing_order if role.billing_order is not None else 9999,
        )
    )
    leads: list[str] = []
    for role in actors:
        name = role.person.name
        if name and name not in leads:
            leads.append(name)
        if len(leads) >= limit:
            break
    return leads


def _normalized_genre_set(movie: Movie) -> set[str]:
    return {_normalize_label(genre) for genre in _movie_genres(movie) if genre}


def _plot_blob(movie: Movie) -> str:
    return (movie.plot or "").lower()


def _plot_has_any(movie: Movie, keywords: tuple[str, ...]) -> bool:
    plot = _plot_blob(movie)
    return any(keyword in plot for keyword in keywords)


def _decade_range(year: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    if year is None:
        return None, None
    decade_start = (year // 10) * 10
    return decade_start, decade_start + 9


def _filters_from_movie(movie: Movie) -> dict[str, object]:
    year_min, year_max = _decade_range(movie.year)
    filters = PickerFilters.from_values(
        genres=_movie_genres(movie),
        moods=_movie_moods(movie),
        year_min=year_min,
        year_max=year_max,
    )
    return filters.to_payload()


def _normalize_label(value: Optional[str]) -> str:
    return value.strip().lower() if isinstance(value, str) and value.strip() else ""


def _shared_labels(primary: list[str], secondary: list[str]) -> list[str]:
    secondary_set = {_normalize_label(label) for label in secondary if label}
    shared: list[str] = []
    for label in primary:
        if _normalize_label(label) in secondary_set and label not in shared:
            shared.append(label)
    return shared


def _pair_theme(primary: Movie, secondary: Movie) -> Tuple[float, Optional[str]]:
    label_candidates: list[Tuple[int, str]] = []

    def add_label(weight: int, label: Optional[str]) -> None:
        if label:
            label_candidates.append((weight, label))

    primary_collection = _normalize_label(getattr(primary, "collection", None))
    secondary_collection = _normalize_label(getattr(secondary, "collection", None))
    if primary_collection and primary_collection == secondary_collection:
        add_label(22, f"Shared Universe: {primary.collection}")

    shared_directors = _shared_labels(_movie_directors(primary), _movie_directors(secondary))
    if shared_directors:
        add_label(22, f"Director Double: {shared_directors[0]}")

    shared_leads = _shared_labels(_movie_leads(primary), _movie_leads(secondary))
    if shared_leads:
        add_label(21, f"Lead Actor Double: {shared_leads[0]}")

    primary_genres = _movie_genres(primary)
    secondary_genres = _movie_genres(secondary)
    primary_genre_set = _normalized_genre_set(primary)
    secondary_genre_set = _normalized_genre_set(secondary)
    shared_genres = _shared_labels(primary_genres, secondary_genres)

    action_labels = {"action", "adventure", "fantasy", "sci-fi", "sci fi", "science fiction"}
    drama_labels = {"drama", "comedy", "family", "romance"}
    crime_labels = {"crime", "thriller"}
    rise_fall_genres = {"crime", "drama", "biography"}

    heist_keywords = ("heist", "robbery", "bank", "vault", "caper")
    coming_of_age_keywords = (
        "coming of age",
        "teen",
        "teenager",
        "high school",
        "growing up",
        "graduation",
        "college",
        "prom",
    )
    rise_fall_keywords = (
        "rise to power",
        "downfall",
        "corruption",
        "empire",
        "crime boss",
        "mob",
        "cartel",
        "kingpin",
        "underworld",
        "crime lord",
        "gangster",
        "mafia",
        "syndicate",
    )
    superhero_keywords = (
        "superhero",
        "super hero",
        "super-powered",
        "superhuman",
        "masked vigilante",
        "vigilante",
    )

    heist_primary = _plot_has_any(primary, heist_keywords)
    heist_secondary = _plot_has_any(secondary, heist_keywords)
    if (heist_primary and heist_secondary) or (
        (heist_primary or heist_secondary)
        and (crime_labels & primary_genre_set)
        and (crime_labels & secondary_genre_set)
    ):
        add_label(21, "Heist Night")

    if "animation" in primary_genre_set and "animation" in secondary_genre_set:
        add_label(22, "Animation Double")

    # Space Odyssey disabled for now (too broad in current vault).

    coming_primary = _plot_has_any(primary, coming_of_age_keywords)
    coming_secondary = _plot_has_any(secondary, coming_of_age_keywords)
    if (coming_primary and coming_secondary) or (
        (coming_primary or coming_secondary)
        and (drama_labels & primary_genre_set)
        and (drama_labels & secondary_genre_set)
    ):
        add_label(21, "Coming-of-Age Double")

    rise_primary = _plot_has_any(primary, rise_fall_keywords)
    rise_secondary = _plot_has_any(secondary, rise_fall_keywords)
    if (rise_primary and rise_secondary) or (
        (rise_primary or rise_secondary)
        and (rise_fall_genres & primary_genre_set)
        and (rise_fall_genres & secondary_genre_set)
    ):
        add_label(21, "Rise & Fall Double")

    superhero_primary = (
        _plot_has_any(primary, superhero_keywords) or "superhero" in primary_genre_set
    )
    superhero_secondary = (
        _plot_has_any(secondary, superhero_keywords) or "superhero" in secondary_genre_set
    )
    if (
        superhero_primary
        and superhero_secondary
        and (action_labels & primary_genre_set)
        and (action_labels & secondary_genre_set)
    ):
        add_label(22, "Superhero Combo")

    if shared_genres:
        if any(_normalize_label(g) == "comedy" for g in shared_genres):
            add_label(18, "Comedy Team-Up")
        else:
            add_label(16, f"Shared Genre: {shared_genres[0]}")

    primary_moods = _movie_moods(primary)
    secondary_moods = _movie_moods(secondary)
    shared_moods = _shared_labels(primary_moods, secondary_moods)
    if shared_moods:
        add_label(12, f"Shared Mood: {shared_moods[0]}")

    decade_min, decade_max = _decade_range(primary.year)
    if decade_min is not None and secondary.year is not None:
        if decade_min <= secondary.year <= (decade_max or decade_min):
            add_label(8, f"Same Decade: {decade_min}s")

    if label_candidates:
        label_candidates.sort(key=lambda item: item[0], reverse=True)
        theme_label = label_candidates[0][1]
        theme_score = float(label_candidates[0][0])
    else:
        theme_label = None
        theme_score = 0.0

    return theme_score, theme_label


def _format_runtime_label(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours <= 0:
        return f"{minutes} min"
    if minutes == 0:
        return f"{hours} hr" if hours == 1 else f"{hours} hrs"
    hour_label = "hr" if hours == 1 else "hrs"
    return f"{hours} {hour_label} {minutes} min"


def _complement_score(candidate: Movie, *, filters: dict[str, object]) -> float:
    payload = PickerCandidate.from_iterables(
        genres=_movie_genres(candidate),
        moods=_movie_moods(candidate),
        runtime=candidate.runtime,
        year=candidate.year,
    ).to_payload()
    score, _ = calculate_flic_score(payload, filters)
    return score


def _shuffle_equal_scores(ranked: list[tuple[float, int]], rng: Random) -> list[tuple[float, int]]:
    if not ranked:
        return ranked
    shuffled: list[tuple[float, int]] = []
    start = 0
    while start < len(ranked):
        score = ranked[start][0]
        end = start + 1
        while end < len(ranked) and ranked[end][0] == score:
            end += 1
        group = ranked[start:end]
        if len(group) > 1:
            rng.shuffle(group)
        shuffled.extend(group)
        start = end
    return shuffled


def pick_double_feature(
    db: Session,
    *,
    runtime_cap: int,
    genre: Optional[str] = None,
    mood: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    seed: Optional[int] = None,
) -> Optional[DoubleFeatureSelection]:
    base_query = (
        db.query(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .filter(Movie.runtime.isnot(None))
        .filter(Movie.runtime <= runtime_cap)
    )

    if genre:
        base_query = base_query.filter(Movie.genres.any(Genre.name == genre))
    if mood:
        base_query = base_query.filter(Movie.moods.any(Mood.name == mood))
    if year_min is not None:
        base_query = base_query.filter(Movie.year >= year_min)
    if year_max is not None:
        base_query = base_query.filter(Movie.year <= year_max)

    filters = PickerFilters.from_values(
        genres=[genre] if genre else (),
        moods=[mood] if mood else (),
        runtime_max=runtime_cap,
        year_min=year_min,
        year_max=year_max,
    ).to_payload()

    ranked = rank_movie_ids_by_flic(db, base_query=base_query, filters=filters)
    if len(ranked) < 2:
        return None

    if seed is not None:
        rng = Random(seed)
    elif settings.double_feature_rotate:
        rng = Random()
    else:
        rng = Random(date.today().toordinal())

    ranked = _shuffle_equal_scores(ranked, rng)

    # Limit to a reasonable pool for pairing.
    top_ranked = ranked[: min(120, len(ranked))]
    ranked_ids = [movie_id for _, movie_id in top_ranked]
    ranked_scores = {movie_id: score for score, movie_id in top_ranked}

    ranked_movies = fetch_movies_in_rank_order(
        db,
        ranked_ids=ranked_ids,
        options=[
            selectinload(Movie.genres),
            selectinload(Movie.moods),
            selectinload(Movie.roles).selectinload(Role.person),
        ],
    )

    ranked_by_id = {movie.id: movie for movie in ranked_movies if movie.id is not None}
    ordered_movies = [ranked_by_id[movie_id] for movie_id in ranked_ids if movie_id in ranked_by_id]

    candidate_pairs: list[Tuple[float, float, int, DoubleFeatureSelection]] = []

    for idx, primary in enumerate(ordered_movies):
        if primary.runtime is None:
            continue
        primary_runtime = primary.runtime
        remaining = runtime_cap - primary_runtime
        if remaining <= 0:
            continue

        primary_score = ranked_scores.get(primary.id, 0.0)
        complement_filters = _filters_from_movie(primary)

        for secondary in ordered_movies[idx + 1 :]:
            if secondary.id == primary.id or secondary.runtime is None:
                continue
            total_runtime = primary_runtime + secondary.runtime
            if total_runtime > runtime_cap:
                continue

            complement_score = _complement_score(secondary, filters=complement_filters)
            theme_score, theme_label = _pair_theme(primary, secondary)
            candidate_score = primary_score + complement_score + float(theme_score)
            candidate_pairs.append(
                (
                    float(theme_score),
                    candidate_score,
                    total_runtime,
                    DoubleFeatureSelection(
                        primary=primary,
                        secondary=secondary,
                        runtime_cap=runtime_cap,
                        total_runtime=_format_runtime_label(total_runtime),
                        theme_label=theme_label,
                    ),
                )
            )

    if not candidate_pairs:
        return None

    themed_pairs = [pair for pair in candidate_pairs if pair[0] > 0]
    if themed_pairs:
        candidate_pairs = themed_pairs

    # Sort by composite score and pick a rotating entry from strong theme buckets.
    candidate_pairs.sort(key=lambda item: (item[1], item[2]), reverse=True)
    if len(candidate_pairs) == 1:
        return candidate_pairs[0][3]

    category_entries: dict[str, list[tuple[float, int, DoubleFeatureSelection]]] = {}
    for theme_score, composite_score, total_runtime, selection in candidate_pairs:
        label = selection.theme_label
        if not label:
            continue
        category = label.split(":", 1)[0].strip()
        category_entries.setdefault(category, []).append(
            (composite_score, total_runtime, selection)
        )

    if category_entries:
        for entries in category_entries.values():
            entries.sort(key=lambda item: (item[0], item[1]), reverse=True)
        categories = sorted(
            category_entries.keys(),
            key=lambda category: (
                category_entries[category][0][0],
                category_entries[category][0][1],
            ),
            reverse=True,
        )
        category_pool = categories[: min(8, len(categories))]
        chosen_category = rng.choice(category_pool)
        top_entries = category_entries[chosen_category][
            : min(3, len(category_entries[chosen_category]))
        ]
        return rng.choice(top_entries)[2]

    top_pairs = candidate_pairs[: min(10, len(candidate_pairs))]
    index = rng.randrange(len(top_pairs))
    return top_pairs[index][3]


__all__ = ["DEFAULT_DOUBLE_FEATURE_RUNTIME", "DoubleFeatureSelection", "pick_double_feature"]
