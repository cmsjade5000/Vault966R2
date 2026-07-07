from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Sequence
from urllib.parse import urlencode

from sqlalchemy.orm import Session, selectinload

from api.models.movie import Movie
from api.services.trusted_movies import trusted_movie_query


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
    variety: bool = False


@dataclass(frozen=True)
class MatchQuestion:
    id: str
    prompt: str
    options: tuple[MatchOption, MatchOption]


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
    variety: bool


@dataclass(frozen=True)
class MovieMatch:
    movie: Movie
    reasons: tuple[str, ...]


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


QUESTIONS: tuple[MatchQuestion, ...] = (
    MatchQuestion(
        id="vibe",
        prompt="What lane should tonight take?",
        options=(
            MatchOption(
                id="scary",
                label="Scary",
                description="Tension, shadows, and a little dread.",
                genres=("Horror", "Thriller"),
                moods=("Scary", "Atmospheric"),
            ),
            MatchOption(
                id="funny",
                label="Funny",
                description="Jokes, charm, and an easier landing.",
                genres=("Comedy",),
                moods=("Funny", "Light"),
            ),
        ),
    ),
    MatchQuestion(
        id="runtime",
        prompt="How much movie do you want?",
        options=(
            MatchOption(
                id="short",
                label="Short",
                description="Keep it tight.",
                runtime_max=100,
            ),
            MatchOption(
                id="long",
                label="Long",
                description="Settle in for a bigger swing.",
                runtime_min=125,
            ),
        ),
    ),
    MatchQuestion(
        id="era",
        prompt="Which shelf feels better?",
        options=(
            MatchOption(
                id="newer",
                label="Newer",
                description="Modern pacing and recent releases.",
                year_min=2000,
            ),
            MatchOption(
                id="older",
                label="Older",
                description="Earlier favorites and older textures.",
                year_max=1999,
            ),
        ),
    ),
    MatchQuestion(
        id="energy",
        prompt="What kind of energy?",
        options=(
            MatchOption(
                id="light",
                label="Light",
                description="Easy, warm, or playful.",
                genres=("Animation", "Family", "Comedy"),
                moods=("Light", "Cozy", "Family", "Romantic"),
            ),
            MatchOption(
                id="intense",
                label="Intense",
                description="Louder, sharper, or more absorbing.",
                genres=("Action", "Crime", "Thriller"),
                moods=("Intense", "Gritty", "High-energy", "Bleak"),
            ),
        ),
    ),
    MatchQuestion(
        id="finish",
        prompt="Last move?",
        options=(
            MatchOption(
                id="surprise",
                label="Surprise me",
                description="Keep the answers, but loosen the final cut.",
                variety=True,
            ),
            MatchOption(
                id="keep",
                label="Keep narrowing",
                description="Stay close to every answer.",
            ),
        ),
    ),
)

_OPTION_BY_ID = {option.id: option for question in QUESTIONS for option in question.options}


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


def next_answer_query(answers: Sequence[str], answer_id: str) -> str:
    return ",".join((*answers, answer_id))


def previous_answers(answers: Sequence[str]) -> tuple[str, ...]:
    return tuple(answers[:-1])


def build_preferences(answer_ids: Sequence[str]) -> MatchPreferences:
    labels: list[str] = []
    genres: list[str] = []
    moods: list[str] = []
    runtime_min: int | None = None
    runtime_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    variety = False

    for answer_id in normalize_answer_ids(answer_ids):
        option = _OPTION_BY_ID[answer_id]
        labels.append(option.label)
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
        variety = variety or option.variety

    return MatchPreferences(
        answer_ids=tuple(answer_ids),
        labels=tuple(labels),
        genres=_dedupe(genres),
        moods=_dedupe(moods),
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        year_min=year_min,
        year_max=year_max,
        variety=variety,
    )


def build_match_result(
    db: Session,
    *,
    answer_ids: str | Sequence[str] | None = None,
    reroll: int = 0,
    shortlist_size: int = 6,
) -> MatchResult:
    answers = normalize_answer_ids(answer_ids)
    preferences = build_preferences(answers)
    movies = (
        trusted_movie_query(db).options(selectinload(Movie.genres), selectinload(Movie.moods)).all()
    )
    trusted_pool_count = len(movies)
    candidate_count = len(_hard_candidate_pool(movies, answers))
    strict_match_count = len(_strict_candidate_pool(movies, answers))
    step_states = _build_step_states(movies, answers)
    complete = len(answers) >= len(QUESTIONS)
    current_question = None if complete else QUESTIONS[len(answers)]
    if not complete:
        return MatchResult(
            answers=answers,
            answered_labels=preferences.labels,
            current_question=current_question,
            trusted_pool_count=trusted_pool_count,
            candidate_count=candidate_count,
            strict_match_count=strict_match_count,
            option_states=_build_option_states(movies, answers, current_question),
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
        )

    candidates, fallback_tier, fallback_notice = _candidate_pool(movies, preferences)
    widened = fallback_tier != "exact"
    result_quality = _result_quality(fallback_tier, preferences, strict_match_count)
    if result_quality == "softened" and fallback_notice is None:
        fallback_notice = (
            "The Vault treated mood as a ranking signal while keeping your lane, runtime, "
            "and era."
        )
    ranked = _rank_movies(candidates, preferences, reroll=reroll)
    selected = ranked[: max(1, shortlist_size + 1)]
    if fallback_tier != "catalog" and len(selected) < shortlist_size + 1:
        selected_ids = {match.movie.id for match in selected}
        extras = [
            match
            for match in _rank_movies(movies, preferences, reroll=reroll)
            if match.movie.id not in selected_ids
        ]
        selected.extend(extras[: shortlist_size + 1 - len(selected)])
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
        reroll_pool_size=len(candidates),
        library_filter_query=_library_filter_query(preferences),
        lead=lead,
        supporting=supporting,
        widened=widened,
        fallback_tier=fallback_tier,
        fallback_notice=fallback_notice,
        complete=True,
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


def _strictly_matches(movie: Movie, preferences: MatchPreferences) -> bool:
    return _matches(movie, preferences)


def _matches(
    movie: Movie,
    preferences: MatchPreferences,
    *,
    relax_moods: bool = False,
    relax_lane: bool = False,
) -> bool:
    genres = _names(getattr(movie, "genres", ()))
    moods = _names(getattr(movie, "moods", ()))
    runtime = getattr(movie, "runtime", None)
    year = getattr(movie, "year", None)

    if not relax_lane and preferences.genres and not genres.intersection(preferences.genres):
        return False
    if not relax_moods and preferences.moods and not moods.intersection(preferences.moods):
        return False
    if preferences.runtime_min is not None and (
        runtime is None or runtime < preferences.runtime_min
    ):
        return False
    if preferences.runtime_max is not None and (
        runtime is None or runtime > preferences.runtime_max
    ):
        return False
    if preferences.year_min is not None and (year is None or year < preferences.year_min):
        return False
    if preferences.year_max is not None and (year is None or year > preferences.year_max):
        return False
    return True


def _candidate_pool(
    movies: Sequence[Movie],
    preferences: MatchPreferences,
) -> tuple[Sequence[Movie], str, str | None]:
    exact = _hard_candidate_pool(movies, preferences.answer_ids)
    if exact:
        return exact, "exact", None
    relaxed_lane = _hard_candidate_pool(movies, preferences.answer_ids, relax_lane=True)
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
) -> list[Movie]:
    options = _answer_options(answer_ids)
    return [
        movie for movie in movies if _matches_answer_options(movie, options, relax_lane=relax_lane)
    ]


def _strict_candidate_pool(movies: Sequence[Movie], answer_ids: Sequence[str]) -> list[Movie]:
    options = _answer_options(answer_ids)
    return [
        movie for movie in movies if _matches_answer_options(movie, options, include_moods=True)
    ]


def _matches_answer_options(
    movie: Movie,
    options: Sequence[MatchOption],
    *,
    include_moods: bool = False,
    relax_lane: bool = False,
) -> bool:
    genres = _names(getattr(movie, "genres", ()))
    moods = _names(getattr(movie, "moods", ()))
    runtime = getattr(movie, "runtime", None)
    year = getattr(movie, "year", None)

    for option in options:
        if not relax_lane and option.genres and not genres.intersection(option.genres):
            return False
        if include_moods and option.moods and not moods.intersection(option.moods):
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
) -> tuple[MatchStepState, ...]:
    states: list[MatchStepState] = []
    accepted: list[str] = []
    for answer_id in normalize_answer_ids(answer_ids):
        question = QUESTIONS[len(accepted)]
        before_count = len(_hard_candidate_pool(movies, accepted))
        accepted.append(answer_id)
        states.append(
            MatchStepState(
                question_id=question.id,
                label=_OPTION_BY_ID[answer_id].label,
                before_count=before_count,
                after_count=len(_hard_candidate_pool(movies, accepted)),
            )
        )
    return tuple(states)


def _build_option_states(
    movies: Sequence[Movie],
    answer_ids: Sequence[str],
    current_question: MatchQuestion | None,
) -> tuple[MatchOptionState, ...]:
    if current_question is None:
        return ()
    before_count = len(_hard_candidate_pool(movies, answer_ids))
    return tuple(
        MatchOptionState(
            option=option,
            before_count=before_count,
            after_count=len(_hard_candidate_pool(movies, (*answer_ids, option.id))),
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
    if preferences.moods and strict_match_count == 0:
        return "softened"
    return "exact"


def _library_filter_query(preferences: MatchPreferences) -> str:
    params: list[tuple[str, str]] = []
    for genre in preferences.genres:
        params.append(("genres", genre))
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
    movies: Sequence[Movie], preferences: MatchPreferences, *, reroll: int
) -> list[MovieMatch]:
    ranked = [
        (
            _score_movie(movie, preferences),
            _stable_tiebreak(movie, preferences, reroll=reroll),
            movie,
        )
        for movie in movies
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        MovieMatch(movie=movie, reasons=_reason_labels(movie, preferences))
        for _, _, movie in ranked
    ]


def _score_movie(movie: Movie, preferences: MatchPreferences) -> float:
    score = 0.0
    genres = _names(getattr(movie, "genres", ()))
    moods = _names(getattr(movie, "moods", ()))
    runtime = getattr(movie, "runtime", None)
    year = getattr(movie, "year", None)

    score += 20.0 * len(genres.intersection(preferences.genres))
    score += 24.0 * len(moods.intersection(preferences.moods))

    if preferences.runtime_max is not None and runtime is not None:
        score += (
            16.0
            if runtime <= preferences.runtime_max
            else -min((runtime - preferences.runtime_max) / 3, 24)
        )
    if preferences.runtime_min is not None and runtime is not None:
        score += (
            16.0
            if runtime >= preferences.runtime_min
            else -min((preferences.runtime_min - runtime) / 3, 24)
        )
    if preferences.year_min is not None and year is not None:
        score += (
            12.0 if year >= preferences.year_min else -min((preferences.year_min - year) / 2, 18)
        )
    if preferences.year_max is not None and year is not None:
        score += (
            12.0 if year <= preferences.year_max else -min((year - preferences.year_max) / 2, 18)
        )

    if getattr(movie, "imdb_rating", None) is not None:
        score += float(movie.imdb_rating or 0) / 2
    if getattr(movie, "rt_score", None) is not None:
        score += float(movie.rt_score or 0) / 25
    if preferences.variety:
        score += _variety_bonus(movie, preferences)
    return score


def _stable_tiebreak(movie: Movie, preferences: MatchPreferences, *, reroll: int) -> str:
    stable_id = getattr(movie, "vault_id", None) or f"movie-{movie.id}"
    raw = f"match:v1|{','.join(preferences.answer_ids)}|{reroll}|{stable_id}"
    return sha256(raw.encode("utf-8")).hexdigest()


def _variety_bonus(movie: Movie, preferences: MatchPreferences) -> float:
    digest = _stable_tiebreak(movie, preferences, reroll=7)
    return int(digest[:2], 16) / 255


def _reason_labels(movie: Movie, preferences: MatchPreferences) -> tuple[str, ...]:
    reasons: list[str] = []
    genres = _names(getattr(movie, "genres", ()))
    moods = _names(getattr(movie, "moods", ()))
    runtime = getattr(movie, "runtime", None)
    year = getattr(movie, "year", None)

    if genres.intersection(preferences.genres):
        reasons.append("Matches the lane")
    if moods.intersection(preferences.moods):
        reasons.append("Fits the mood")
    if (
        preferences.runtime_max is not None
        and runtime is not None
        and runtime <= preferences.runtime_max
    ):
        reasons.append("Keeps it tight")
    if (
        preferences.runtime_min is not None
        and runtime is not None
        and runtime >= preferences.runtime_min
    ):
        reasons.append("Longer watch")
    if preferences.year_min is not None and year is not None and year >= preferences.year_min:
        reasons.append("Newer shelf")
    if preferences.year_max is not None and year is not None and year <= preferences.year_max:
        reasons.append("Older shelf")
    if not reasons:
        reasons.append("Closest trusted match")
    return tuple(reasons[:3])


__all__ = [
    "QUESTIONS",
    "MatchOption",
    "MatchQuestion",
    "MatchResult",
    "build_match_result",
    "build_preferences",
    "next_answer_query",
    "normalize_answer_ids",
    "previous_answers",
]
