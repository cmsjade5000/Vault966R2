from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from hashlib import sha256
from typing import Iterable, Sequence
from urllib.parse import urlencode

from sqlalchemy.orm import Session, selectinload

from api.models.movie import Movie
from api.services.trusted_movies import trusted_movie_query
from core.moods import score_moods

PICK_COUNT = 5

_HIGH_ENERGY_MOODS = frozenset({"High-energy", "Intense", "Scary", "Gritty", "Epic", "Bleak"})
_LOW_ENERGY_MOODS = frozenset({"Cozy", "Light", "Thoughtful", "Atmospheric", "Romantic"})
_HIGH_ENERGY_GENRES = frozenset({"Action", "Adventure", "Crime", "Horror", "Thriller", "War"})
_LOW_ENERGY_GENRES = frozenset(
    {"Animation", "Documentary", "Drama", "Family", "History", "Romance"}
)


@dataclass(frozen=True)
class MatchOption:
    id: str
    label: str
    description: str
    genres: tuple[str, ...] = ()
    moods: tuple[str, ...] = ()
    runtime_min: int | None = None
    runtime_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    energy: str | None = None
    ranking_only: bool = False


@dataclass(frozen=True)
class MatchQuestion:
    id: str
    prompt: str
    options: tuple[MatchOption, ...]


@dataclass(frozen=True)
class MatchPreferences:
    answer_ids: tuple[str, ...]
    labels: tuple[str, ...]
    genres: tuple[str, ...]
    moods: tuple[str, ...]
    runtime_min: int | None
    runtime_max: int | None
    year_min: int | None
    year_max: int | None
    energy: str | None
    mood_label: str | None
    energy_label: str | None
    runtime_label: str | None
    genre_label: str | None
    era_label: str | None


@dataclass(frozen=True)
class MovieMatch:
    movie: Movie
    reasons: tuple[str, ...]
    why_it_fits: str
    synopsis: str


@dataclass
class _MovieFeatures:
    movie: Movie
    genres: frozenset[str]
    stored_moods: frozenset[str]

    @cached_property
    def moods(self) -> frozenset[str]:
        return self.stored_moods.union(_infer_movie_moods(self.movie, set(self.genres)))

    @cached_property
    def energy(self) -> str:
        moods = self.moods
        if moods.intersection(_HIGH_ENERGY_MOODS) or self.genres.intersection(_HIGH_ENERGY_GENRES):
            return "high"
        if moods.intersection(_LOW_ENERGY_MOODS) or self.genres.intersection(_LOW_ENERGY_GENRES):
            return "low"
        return "medium"


_FeatureCache = dict[int, _MovieFeatures]


@dataclass(frozen=True)
class MatchStepState:
    question_id: str
    label: str
    before_count: int
    after_count: int


@dataclass(frozen=True)
class MatchOptionState:
    option: MatchOption
    before_count: int
    after_count: int


@dataclass(frozen=True)
class MatchResult:
    answers: tuple[str, ...]
    answered_labels: tuple[str, ...]
    current_question: MatchQuestion | None
    trusted_pool_count: int
    candidate_count: int
    strict_match_count: int
    option_states: tuple[MatchOptionState, ...]
    step_states: tuple[MatchStepState, ...]
    result_quality: str
    reroll_pool_size: int
    library_filter_query: str
    lead: MovieMatch | None
    supporting: tuple[MovieMatch, ...]
    widened: bool
    fallback_tier: str
    fallback_notice: str | None
    complete: bool
    edit_index: int | None = None


QUESTIONS: tuple[MatchQuestion, ...] = (
    MatchQuestion(
        id="mood",
        prompt="What mood are you after?",
        options=(
            MatchOption(
                id="cozy",
                label="Cozy",
                description="Warm, easygoing, and comfortable.",
                moods=("Cozy", "Light", "Family", "Romantic"),
                ranking_only=True,
            ),
            MatchOption(
                id="funny",
                label="Funny",
                description="Jokes, charm, and a lighter landing.",
                moods=("Funny", "Light"),
                ranking_only=True,
            ),
            MatchOption(
                id="thoughtful",
                label="Thoughtful",
                description="Something absorbing with ideas to chew on.",
                moods=("Thoughtful", "Mind-bending", "Atmospheric"),
                ranking_only=True,
            ),
            MatchOption(
                id="intense",
                label="Intense",
                description="Tension, danger, and a sharper edge.",
                moods=("Intense", "Scary", "Gritty", "Bleak"),
                ranking_only=True,
            ),
            MatchOption(
                id="any_mood",
                label="Any mood",
                description="Leave mood open and let the rest of the night lead.",
                ranking_only=True,
            ),
        ),
    ),
    MatchQuestion(
        id="energy",
        prompt="How much energy should it have?",
        options=(
            MatchOption(
                id="low",
                label="Low-key",
                description="Gentle, measured, or quietly immersive.",
                energy="low",
                ranking_only=True,
            ),
            MatchOption(
                id="balanced",
                label="Balanced",
                description="Enough momentum without going full throttle.",
                energy="medium",
                ranking_only=True,
            ),
            MatchOption(
                id="high",
                label="High-energy",
                description="Fast, forceful, or edge-of-the-seat.",
                energy="high",
                ranking_only=True,
            ),
            MatchOption(
                id="any_energy",
                label="Any energy",
                description="Keep the energy open.",
                ranking_only=True,
            ),
        ),
    ),
    MatchQuestion(
        id="runtime",
        prompt="How long should tonight's watch be?",
        options=(
            MatchOption(
                id="short",
                label="Under 100 minutes",
                description="Keep it tight and leave the night intact.",
                runtime_max=99,
            ),
            MatchOption(
                id="standard",
                label="100–130 minutes",
                description="A full feature without an intermission strategy.",
                runtime_min=100,
                runtime_max=130,
            ),
            MatchOption(
                id="long",
                label="131+ minutes",
                description="Settle in for a bigger swing.",
                runtime_min=131,
            ),
            MatchOption(
                id="any_runtime",
                label="Any runtime",
                description="Let the runtime be a surprise.",
                ranking_only=True,
            ),
        ),
    ),
    MatchQuestion(
        id="genre",
        prompt="Which genre lane sounds best?",
        options=(
            MatchOption(
                id="action",
                label="Action & adventure",
                description="Movement, stakes, and a bigger canvas.",
                genres=("Action", "Adventure"),
            ),
            MatchOption(
                id="comedy",
                label="Comedy",
                description="Let the genre do some of the emotional lifting.",
                genres=("Comedy",),
            ),
            MatchOption(
                id="drama",
                label="Drama",
                description="Character, consequence, and human mess.",
                genres=("Drama",),
            ),
            MatchOption(
                id="family",
                label="Animation & family",
                description="Accessible, imaginative, and crowd-friendly.",
                genres=("Animation", "Family"),
            ),
            MatchOption(
                id="speculative",
                label="Sci-fi & fantasy",
                description="Other worlds, strange rules, and big ideas.",
                genres=("Sci-Fi", "Science Fiction", "Fantasy"),
            ),
            MatchOption(
                id="any_genre",
                label="Any genre",
                description="Keep the genre lane open.",
                ranking_only=True,
            ),
        ),
    ),
    MatchQuestion(
        id="era",
        prompt="Which era should we pull from?",
        options=(
            MatchOption(
                id="classic",
                label="Before 1980",
                description="Classic craft and earlier cinematic textures.",
                year_max=1979,
            ),
            MatchOption(
                id="retro",
                label="1980s & 1990s",
                description="Analog edges, practical effects, and video-store DNA.",
                year_min=1980,
                year_max=1999,
            ),
            MatchOption(
                id="modern",
                label="2000–2014",
                description="Modern filmmaking before the current streaming era.",
                year_min=2000,
                year_max=2014,
            ),
            MatchOption(
                id="recent",
                label="2015 to now",
                description="Contemporary pacing and recent releases.",
                year_min=2015,
            ),
            MatchOption(
                id="any_era",
                label="Any era",
                description="Pull from any era.",
                ranking_only=True,
            ),
        ),
    ),
)

_OPTION_BY_ID = {option.id: option for question in QUESTIONS for option in question.options}
_ANY_OPTION_IDS = tuple(f"any_{question.id}" for question in QUESTIONS)


def normalize_answer_ids(raw_answers: str | Sequence[str] | None) -> tuple[str, ...]:
    if raw_answers is None:
        return ()
    if isinstance(raw_answers, str):
        candidates = [part.strip() for part in raw_answers.split(",")]
    else:
        candidates = [str(part).strip() for part in raw_answers]

    normalized: list[str] = []
    for index, answer_id in enumerate(candidates[: len(QUESTIONS)]):
        if not answer_id:
            break
        if index >= len(QUESTIONS):
            break
        valid_for_step = {option.id for option in QUESTIONS[index].options}
        if answer_id not in valid_for_step:
            break
        normalized.append(answer_id)
    return tuple(normalized)


def next_answer_query(answers: Sequence[str], answer_id: str, edit_index: int | None = None) -> str:
    if edit_index is not None and 0 <= edit_index < len(answers):
        updated = list(answers)
        updated[edit_index] = answer_id
        return ",".join(updated)
    return ",".join((*answers, answer_id))


def previous_answers(answers: Sequence[str]) -> tuple[str, ...]:
    return tuple(answers[:-1])


def complete_answer_ids(answer_ids: Sequence[str]) -> tuple[str, ...]:
    """Fill unanswered dimensions with explicit no-preference options."""

    normalized = normalize_answer_ids(answer_ids)
    return normalized + _ANY_OPTION_IDS[len(normalized) :]


def build_preferences(answer_ids: Sequence[str]) -> MatchPreferences:
    normalized_ids = normalize_answer_ids(answer_ids)
    labels: list[str] = []
    genres: list[str] = []
    moods: list[str] = []
    runtime_min: int | None = None
    runtime_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    energy: str | None = None
    dimension_labels: dict[str, str] = {}

    for index, answer_id in enumerate(normalized_ids):
        option = _OPTION_BY_ID[answer_id]
        question = QUESTIONS[index]
        labels.append(option.label)
        dimension_labels[question.id] = option.label
        genres.extend(option.genres)
        moods.extend(option.moods)
        if option.runtime_min is not None:
            runtime_min = max(runtime_min or option.runtime_min, option.runtime_min)
        if option.runtime_max is not None:
            runtime_max = min(runtime_max or option.runtime_max, option.runtime_max)
        if option.year_min is not None:
            year_min = max(year_min or option.year_min, option.year_min)
        if option.year_max is not None:
            year_max = min(year_max or option.year_max, option.year_max)
        energy = option.energy or energy

    return MatchPreferences(
        answer_ids=normalized_ids,
        labels=tuple(labels),
        genres=_dedupe(genres),
        moods=_dedupe(moods),
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        year_min=year_min,
        year_max=year_max,
        energy=energy,
        mood_label=dimension_labels.get("mood"),
        energy_label=dimension_labels.get("energy"),
        runtime_label=dimension_labels.get("runtime"),
        genre_label=dimension_labels.get("genre"),
        era_label=dimension_labels.get("era"),
    )


def build_match_result(
    db: Session,
    *,
    answer_ids: str | Sequence[str] | None = None,
    reroll: int = 0,
    shortlist_size: int = PICK_COUNT - 1,
    show_picks_now: bool = False,
    edit_index: int | None = None,
) -> MatchResult:
    answers = normalize_answer_ids(answer_ids)
    if show_picks_now:
        answers = complete_answer_ids(answers)
    if edit_index is not None and not (0 <= edit_index < len(answers)):
        edit_index = None
    preferences = build_preferences(answers)
    movies = (
        trusted_movie_query(db).options(selectinload(Movie.genres), selectinload(Movie.moods)).all()
    )
    trusted_pool_count = len(movies)
    feature_cache = _build_feature_cache(movies)
    candidate_answers = answers
    if edit_index is not None:
        candidate_answers = (
            *answers[:edit_index],
            _ANY_OPTION_IDS[edit_index],
            *answers[edit_index + 1 :],
        )
    candidate_count = len(
        _hard_candidate_pool(movies, candidate_answers, feature_cache=feature_cache)
    )
    strict_match_count = len(_strict_candidate_pool(movies, answers, feature_cache=feature_cache))
    step_states = _build_step_states(movies, answers, feature_cache=feature_cache)
    complete = len(answers) >= len(QUESTIONS) and edit_index is None
    current_question = (
        QUESTIONS[edit_index]
        if edit_index is not None
        else (None if complete else QUESTIONS[len(answers)])
    )
    if not complete:
        return MatchResult(
            answers=answers,
            answered_labels=preferences.labels,
            current_question=current_question,
            trusted_pool_count=trusted_pool_count,
            candidate_count=candidate_count,
            strict_match_count=strict_match_count,
            option_states=_build_option_states(
                movies,
                candidate_answers,
                current_question,
                edit_index=edit_index,
                feature_cache=feature_cache,
            ),
            step_states=step_states,
            result_quality="pending",
            reroll_pool_size=candidate_count,
            library_filter_query=_library_filter_query(preferences),
            lead=None,
            supporting=(),
            widened=False,
            fallback_tier="pending",
            fallback_notice=None,
            complete=False,
            edit_index=edit_index,
        )

    candidates, fallback_tier, fallback_notice = _candidate_pool(
        movies, preferences, feature_cache=feature_cache
    )
    widened = fallback_tier != "exact"
    result_quality = _result_quality(fallback_tier, preferences, strict_match_count)
    if result_quality == "softened" and fallback_notice is None:
        fallback_notice = (
            "The Vault used mood and energy to rank the strongest matches while keeping "
            "your genre, runtime, and era."
        )
    # Keep the first recommendation stable, then cycle only the strongest eligible
    # picks. Broader choices used to fill the shortlist must not become the lead.
    ranked = _rank_movies(candidates, preferences, reroll=0, feature_cache=feature_cache)
    pick_count = min(max(shortlist_size + 1, 3), PICK_COUNT)
    eligible = ranked[:pick_count]
    offset = reroll % len(eligible) if eligible else 0
    selected = eligible[offset:] + eligible[:offset]
    if fallback_tier != "catalog" and len(selected) < pick_count:
        exact_count = len(selected)
        selected_ids = {match.movie.id for match in selected}
        extras = [
            match
            for match in _rank_movies(movies, preferences, reroll=0, feature_cache=feature_cache)
            if match.movie.id not in selected_ids
        ]
        selected.extend(extras[: pick_count - len(selected)])
        if len(selected) > exact_count:
            widened = True
            result_quality = "widened"
            fallback_notice = (
                f"The Vault found {exact_count} exact {('match' if exact_count == 1 else 'matches')}, "
                "then filled the shortlist with the closest trusted options."
            )
    lead = selected[0] if selected else None
    supporting = tuple(selected[1:])

    return MatchResult(
        answers=answers,
        answered_labels=preferences.labels,
        current_question=None,
        trusted_pool_count=trusted_pool_count,
        candidate_count=len(candidates),
        strict_match_count=strict_match_count,
        option_states=(),
        step_states=step_states,
        result_quality=result_quality,
        reroll_pool_size=len(eligible),
        library_filter_query=_library_filter_query(preferences),
        lead=lead,
        supporting=supporting,
        widened=widened,
        fallback_tier=fallback_tier,
        fallback_notice=fallback_notice,
        complete=True,
        edit_index=None,
    )


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return tuple(seen)


def _names(items: Iterable[object]) -> set[str]:
    names: set[str] = set()
    for item in items:
        name = getattr(item, "name", None)
        if name:
            names.add(str(name))
    return names


def _movie_moods(movie: Movie, genres: set[str] | None = None) -> set[str]:
    """Combine curated mood tags with deterministic metadata-derived tags."""

    stored = _stored_movie_moods(movie)
    return stored.union(_infer_movie_moods(movie, genres))


def _infer_movie_moods(movie: Movie, genres: set[str] | None = None) -> set[str]:
    genre_names = genres if genres is not None else _names(getattr(movie, "genres", ()))
    return set(
        score_moods(
            genre_names,
            keywords=getattr(movie, "keywords", None),
            plot=getattr(movie, "plot", None),
            certificate=getattr(movie, "certificate", None),
            runtime=getattr(movie, "runtime", None),
        )
    )


def _stored_movie_moods(movie: Movie) -> set[str]:
    """Return curated mood tags suitable for user-facing fit explanations."""

    return _names(getattr(movie, "moods", ()))


def _movie_energy(movie: Movie, *, genres: set[str] | None = None) -> str:
    """Infer an energy lane without adding a database-only energy field."""

    return _features(movie, None).energy


def _build_feature_cache(movies: Sequence[Movie]) -> _FeatureCache:
    cache: _FeatureCache = {}
    for movie in movies:
        genres = _names(getattr(movie, "genres", ()))
        stored_moods = _stored_movie_moods(movie)
        cache[id(movie)] = _MovieFeatures(
            movie=movie,
            genres=frozenset(genres),
            stored_moods=frozenset(stored_moods),
        )
    return cache


def _features(movie: Movie, feature_cache: _FeatureCache | None) -> _MovieFeatures:
    if feature_cache is not None and id(movie) in feature_cache:
        return feature_cache[id(movie)]
    genres = _names(getattr(movie, "genres", ()))
    stored_moods = _stored_movie_moods(movie)
    return _MovieFeatures(
        movie=movie,
        genres=frozenset(genres),
        stored_moods=frozenset(stored_moods),
    )


def _candidate_pool(
    movies: Sequence[Movie],
    preferences: MatchPreferences,
    *,
    feature_cache: _FeatureCache | None = None,
) -> tuple[Sequence[Movie], str, str | None]:
    exact = _hard_candidate_pool(movies, preferences.answer_ids, feature_cache=feature_cache)
    if exact:
        return exact, "exact", None
    relaxed_lane = _hard_candidate_pool(
        movies, preferences.answer_ids, relax_lane=True, feature_cache=feature_cache
    )
    if relaxed_lane:
        return (
            relaxed_lane,
            "relaxed_lane",
            "The Vault kept your runtime and era, then widened the lane.",
        )
    return (
        movies,
        "catalog",
        "The Vault widened to trusted titles because no movie hit the selected path.",
    )


def _answer_options(answer_ids: Sequence[str]) -> tuple[MatchOption, ...]:
    return tuple(_OPTION_BY_ID[answer_id] for answer_id in normalize_answer_ids(answer_ids))


def _hard_candidate_pool(
    movies: Sequence[Movie],
    answer_ids: Sequence[str],
    *,
    relax_lane: bool = False,
    feature_cache: _FeatureCache | None = None,
) -> list[Movie]:
    options = _answer_options(answer_ids)
    return [
        movie
        for movie in movies
        if _matches_answer_options(
            movie, options, relax_lane=relax_lane, feature_cache=feature_cache
        )
    ]


def _strict_candidate_pool(
    movies: Sequence[Movie],
    answer_ids: Sequence[str],
    *,
    feature_cache: _FeatureCache | None = None,
) -> list[Movie]:
    options = _answer_options(answer_ids)
    return [
        movie
        for movie in movies
        if _matches_answer_options(movie, options, include_moods=True, feature_cache=feature_cache)
    ]


def _matches_answer_options(
    movie: Movie,
    options: Sequence[MatchOption],
    *,
    include_moods: bool = False,
    relax_lane: bool = False,
    feature_cache: _FeatureCache | None = None,
) -> bool:
    movie_features = _features(movie, feature_cache)
    genres = movie_features.genres
    moods = movie_features.stored_moods
    runtime = getattr(movie, "runtime", None)
    year = getattr(movie, "year", None)

    for option in options:
        if not relax_lane and option.genres and not genres.intersection(option.genres):
            return False
        if include_moods and option.moods and not moods.intersection(option.moods):
            return False
        if include_moods and option.energy and option.energy != movie_features.energy:
            return False
        if option.runtime_min is not None and (runtime is None or runtime < option.runtime_min):
            return False
        if option.runtime_max is not None and (runtime is None or runtime > option.runtime_max):
            return False
        if option.year_min is not None and (year is None or year < option.year_min):
            return False
        if option.year_max is not None and (year is None or year > option.year_max):
            return False
    return True


def _build_step_states(
    movies: Sequence[Movie],
    answer_ids: Sequence[str],
    *,
    feature_cache: _FeatureCache | None = None,
) -> tuple[MatchStepState, ...]:
    states: list[MatchStepState] = []
    accepted: list[str] = []
    for answer_id in normalize_answer_ids(answer_ids):
        question = QUESTIONS[len(accepted)]
        before_count = len(_hard_candidate_pool(movies, accepted, feature_cache=feature_cache))
        accepted.append(answer_id)
        states.append(
            MatchStepState(
                question_id=question.id,
                label=_OPTION_BY_ID[answer_id].label,
                before_count=before_count,
                after_count=len(
                    _hard_candidate_pool(movies, accepted, feature_cache=feature_cache)
                ),
            )
        )
    return tuple(states)


def _build_option_states(
    movies: Sequence[Movie],
    answer_ids: Sequence[str],
    current_question: MatchQuestion | None,
    *,
    edit_index: int | None = None,
    feature_cache: _FeatureCache | None = None,
) -> tuple[MatchOptionState, ...]:
    if current_question is None:
        return ()
    before_count = len(_hard_candidate_pool(movies, answer_ids, feature_cache=feature_cache))
    return tuple(
        MatchOptionState(
            option=option,
            before_count=before_count,
            after_count=len(
                _hard_candidate_pool(
                    movies,
                    (
                        (*answer_ids[:edit_index], option.id, *answer_ids[edit_index + 1 :])
                        if edit_index is not None
                        else (*answer_ids, option.id)
                    ),
                    feature_cache=feature_cache,
                )
            ),
        )
        for option in current_question.options
    )


def _result_quality(
    fallback_tier: str,
    preferences: MatchPreferences,
    strict_match_count: int,
) -> str:
    if fallback_tier != "exact":
        return "widened"
    if (preferences.moods or preferences.energy) and strict_match_count == 0:
        return "softened"
    return "exact"


def _library_filter_query(preferences: MatchPreferences) -> str:
    params: list[tuple[str, str]] = []
    # A picker genre option may include aliases or an adjacent lane, while Library
    # genre query parameters are ANDed. Use the primary label to avoid over-filtering.
    if preferences.genres:
        params.append(("genres", preferences.genres[0]))
    if preferences.runtime_min is not None:
        params.append(("runtime_min", str(preferences.runtime_min)))
    if preferences.runtime_max is not None:
        params.append(("runtime_max", str(preferences.runtime_max)))
    if preferences.year_min is not None:
        params.append(("year_min", str(preferences.year_min)))
    if preferences.year_max is not None:
        params.append(("year_max", str(preferences.year_max)))
    return urlencode(params)


def _rank_movies(
    movies: Sequence[Movie],
    preferences: MatchPreferences,
    *,
    reroll: int,
    feature_cache: _FeatureCache | None = None,
) -> list[MovieMatch]:
    ranked = [
        (
            _score_movie(movie, preferences, feature_cache=feature_cache),
            _quality_score(movie),
            _stable_tiebreak(movie, preferences, reroll=reroll),
            movie,
        )
        for movie in movies
    ]
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [
        MovieMatch(
            movie=movie,
            reasons=_reason_labels(movie, preferences, feature_cache=feature_cache),
            why_it_fits=_why_it_fits(movie, preferences, feature_cache=feature_cache),
            synopsis=_concise_synopsis(movie),
        )
        for _, _, _, movie in ranked
    ]


def _score_movie(
    movie: Movie,
    preferences: MatchPreferences,
    *,
    feature_cache: _FeatureCache | None = None,
) -> float:
    score = 0.0
    movie_features = _features(movie, feature_cache)
    genres = movie_features.genres
    moods = movie_features.moods if preferences.moods else frozenset()
    runtime = getattr(movie, "runtime", None)
    year = getattr(movie, "year", None)

    if genres.intersection(preferences.genres):
        score += 24.0
    if moods.intersection(preferences.moods):
        score += 24.0
    if preferences.energy:
        energy_distance = abs(
            {"low": 0, "medium": 1, "high": 2}[movie_features.energy]
            - {"low": 0, "medium": 1, "high": 2}[preferences.energy]
        )
        score += 20.0 if energy_distance == 0 else (5.0 if energy_distance == 1 else -8.0)

    if preferences.runtime_min is not None or preferences.runtime_max is not None:
        if runtime is None:
            score -= 12.0
        elif (preferences.runtime_min is None or runtime >= preferences.runtime_min) and (
            preferences.runtime_max is None or runtime <= preferences.runtime_max
        ):
            score += 16.0
        elif preferences.runtime_min is not None and runtime < preferences.runtime_min:
            score -= min((preferences.runtime_min - runtime) / 3, 24)
        elif preferences.runtime_max is not None:
            score -= min((runtime - preferences.runtime_max) / 3, 24)

    if preferences.year_min is not None or preferences.year_max is not None:
        if year is None:
            score -= 10.0
        elif (preferences.year_min is None or year >= preferences.year_min) and (
            preferences.year_max is None or year <= preferences.year_max
        ):
            score += 12.0
        elif preferences.year_min is not None and year < preferences.year_min:
            score -= min((preferences.year_min - year) / 2, 18)
        elif preferences.year_max is not None:
            score -= min((year - preferences.year_max) / 2, 18)
    return score


def _quality_score(movie: Movie) -> float:
    """Use ratings only to break equal preference-fit scores."""

    imdb = float(getattr(movie, "imdb_rating", None) or 0) * 10
    rt = float(getattr(movie, "rt_score", None) or 0)
    return max(imdb, rt)


def _stable_tiebreak(movie: Movie, preferences: MatchPreferences, *, reroll: int) -> str:
    stable_id = getattr(movie, "vault_id", None) or f"movie-{movie.id}"
    raw = f"match:v1|{','.join(preferences.answer_ids)}|{reroll}|{stable_id}"
    return sha256(raw.encode("utf-8")).hexdigest()


def _fit_fragments(
    movie: Movie,
    preferences: MatchPreferences,
    *,
    feature_cache: _FeatureCache | None = None,
) -> list[str]:
    fragments: list[str] = []
    movie_features = _features(movie, feature_cache)
    genres = movie_features.genres
    moods = movie_features.stored_moods
    runtime = getattr(movie, "runtime", None)
    year = getattr(movie, "year", None)

    if preferences.mood_label and moods.intersection(preferences.moods):
        fragments.append(f"{preferences.mood_label} mood")
    if (
        preferences.energy
        and preferences.energy_label
        and preferences.energy == movie_features.energy
    ):
        fragments.append(f"{preferences.energy_label} energy")
    if (
        preferences.runtime_label
        and (preferences.runtime_min is not None or preferences.runtime_max is not None)
        and runtime is not None
        and (preferences.runtime_min is None or runtime >= preferences.runtime_min)
        and (preferences.runtime_max is None or runtime <= preferences.runtime_max)
    ):
        fragments.append(f"{runtime}-minute runtime")
    if preferences.genre_label and genres.intersection(preferences.genres):
        fragments.append(preferences.genre_label)
    if (
        preferences.era_label
        and (preferences.year_min is not None or preferences.year_max is not None)
        and year is not None
        and (preferences.year_min is None or year >= preferences.year_min)
        and (preferences.year_max is None or year <= preferences.year_max)
    ):
        fragments.append(f"{year} fits {preferences.era_label}")
    return fragments


def _reason_labels(
    movie: Movie,
    preferences: MatchPreferences,
    *,
    feature_cache: _FeatureCache | None = None,
) -> tuple[str, ...]:
    fragments = _fit_fragments(movie, preferences, feature_cache=feature_cache)
    return tuple(fragments[:3] or ["Closest trusted match"])


def _why_it_fits(
    movie: Movie,
    preferences: MatchPreferences,
    *,
    feature_cache: _FeatureCache | None = None,
) -> str:
    fragments = _fit_fragments(movie, preferences, feature_cache=feature_cache)[:3]
    if not fragments:
        return "Closest trusted option after widening the selected preferences."
    if len(fragments) == 1:
        detail = fragments[0]
    else:
        detail = f"{', '.join(fragments[:-1])}, and {fragments[-1]}"
    return f"{detail[0].upper()}{detail[1:]}."


def _concise_synopsis(movie: Movie, *, limit: int = 220) -> str:
    synopsis = " ".join(str(getattr(movie, "plot", None) or "").split())
    if len(synopsis) <= limit:
        return synopsis
    clipped = synopsis[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{clipped}…"


__all__ = [
    "QUESTIONS",
    "MatchOption",
    "MatchQuestion",
    "MatchResult",
    "build_match_result",
    "build_preferences",
    "complete_answer_ids",
    "next_answer_query",
    "normalize_answer_ids",
    "previous_answers",
]
