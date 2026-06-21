from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_profile_role, require_same_origin
from api.models.movie import Movie, MovieIngestProvenance
from api.models.movie_flag import MovieFlag
from api.models.source_sync import SourceFieldDecision
from api.schemas.movie import (
    MovieLookupResponse,
    MovieMatchApplyResponse,
    MovieMatchSelection,
    MovieUpdate,
)
from api.services.movie_lookup import (
    MovieLookupError,
    MovieLookupNotFound,
    MovieLookupUnavailable,
    lookup_movie_candidates,
    lookup_omdb_candidates,
)
from api.services.movie_flags import clear_movie_flag
from api.services.movie_review import (
    detect_review_issues,
    get_review_queue,
    mark_all_review_items_needs_fix,
    record_review_decision,
)
from api.services.movie_updates import apply_movie_update
from api.services.source_sync import (
    SourceSyncError,
    accept_all_source_differences,
    assign_source_row_match,
    create_movie_from_source_row,
    decide_source_field,
    defer_source_row_for_research,
    dismiss_duplicate,
    get_source_review_queue,
    latest_active_snapshot,
    partition_source_review_queue,
    source_bulk_decision_counts,
    undo_source_field_decision,
)
from api.services.profiles import (
    ROLE_ADMIN,
    get_active_profile_role,
    get_active_profile_id,
    get_profiles,
)

router = APIRouter(tags=["ui"])
SOURCE_REVIEW_VIEWS = {
    "differences",
    "research",
    "ambiguous",
    "new",
    "duplicates",
}
REVIEW_VIEWS = {
    *SOURCE_REVIEW_VIEWS,
    "vault",
    "flags",
}
REVIEW_TABS = [
    ("differences", "Differences"),
    ("research", "Needs research"),
    ("ambiguous", "Ambiguous"),
    ("new", "New movies"),
    ("duplicates", "Duplicates"),
    ("vault", "Vault checks"),
    ("flags", "Flags"),
]


def _load_review_inventory(db: Session, *, flag_reason: str | None = None) -> dict:
    queue, finding_count = get_review_queue(db)
    all_flags = (
        db.query(MovieFlag)
        .options(joinedload(MovieFlag.movie), joinedload(MovieFlag.reported_by_profile))
        .order_by(desc(MovieFlag.updated_at), MovieFlag.movie_id.asc())
        .all()
    )
    flag_reasons = sorted({flag.reason for flag in all_flags if flag.reason})
    selected_flag_reason = flag_reason if flag_reason in flag_reasons else None
    flags = [
        flag
        for flag in all_flags
        if selected_flag_reason is None or flag.reason == selected_flag_reason
    ]
    source_groups = partition_source_review_queue(get_source_review_queue(db))
    review_counts = {
        **{name: len(items) for name, items in source_groups.items()},
        "vault": len(queue),
        "flags": len(all_flags),
    }
    return {
        "queue": queue,
        "finding_count": finding_count,
        "all_flags": all_flags,
        "flags": flags,
        "flag_reasons": flag_reasons,
        "selected_flag_reason": selected_flag_reason,
        "source_groups": source_groups,
        "review_counts": review_counts,
    }


def _default_review_view(requested_view: str | None, review_counts: dict[str, int]) -> str:
    view = requested_view or "differences"
    if view not in REVIEW_VIEWS:
        raise HTTPException(status_code=404, detail="Review category not found")
    if requested_view is None and review_counts[view] == 0:
        return next((key for key, _ in REVIEW_TABS if review_counts[key]), view)
    return view


def _selected_review_queue(view: str, inventory: dict) -> list:
    if view == "vault":
        return inventory["queue"]
    if view == "flags":
        return inventory["flags"]
    return inventory["source_groups"][view]


def _review_item_id(view: str, item) -> int:
    if view == "vault":
        return item.movie.id
    if view == "flags":
        return item.movie_id
    return item.source_row.id


def _review_navigation_context(
    *,
    view: str,
    selected_queue: list,
    requested_item_id: int | None,
    selected_flag_reason: str | None,
) -> dict:
    selected_index = 0
    if requested_item_id is not None:
        selected_index = next(
            (
                index
                for index, item in enumerate(selected_queue)
                if _review_item_id(view, item) == requested_item_id
            ),
            0,
        )
    review_item = selected_queue[selected_index] if selected_queue else None
    item_param = "movie" if view in {"vault", "flags"} else "row"
    previous_item = selected_queue[selected_index - 1] if selected_index > 0 else None
    next_item = (
        selected_queue[selected_index + 1] if selected_index + 1 < len(selected_queue) else None
    )

    def item_url(item) -> str | None:
        if item is None:
            return None
        item_id = _review_item_id(view, item)
        params = [f"view={quote(view)}", f"{item_param}={item_id}"]
        if view == "flags" and selected_flag_reason:
            params.append(f"flag_reason={quote(selected_flag_reason, safe='')}")
        return f"/ui/movies/health?{'&'.join(params)}#review-workbench"

    return {
        "review_item": review_item,
        "review_position": selected_index + 1 if review_item else 0,
        "review_queue_count": len(selected_queue),
        "previous_item_url": item_url(previous_item),
        "next_item_url": item_url(next_item),
    }


def build_review_context(
    request: Request,
    db: Session,
    *,
    view: str | None,
    row: int | None,
    movie: int | None,
    undo_decision: int | None,
    flag_reason: str | None = None,
) -> dict:
    inventory = _load_review_inventory(db, flag_reason=flag_reason)
    review_counts = inventory["review_counts"]
    view = _default_review_view(view, review_counts)
    review_view_label = dict(REVIEW_TABS)[view]
    selected_queue = _selected_review_queue(view, inventory)
    requested_item_id = movie if view in {"vault", "flags"} else row
    navigation = _review_navigation_context(
        view=view,
        selected_queue=selected_queue,
        requested_item_id=requested_item_id,
        selected_flag_reason=inventory["selected_flag_reason"],
    )
    next_nonempty_view = next(
        ((key, label) for key, label in REVIEW_TABS if key != view and review_counts[key]),
        None,
    )
    source_snapshot = latest_active_snapshot(db)
    bulk_source_field_count, bulk_source_skipped_count = source_bulk_decision_counts(
        db,
        snapshot=source_snapshot,
    )
    undo_record = db.get(SourceFieldDecision, undo_decision) if undo_decision else None
    if undo_record is not None and undo_record.undone_at is not None:
        undo_record = None
    return {
        "queue": inventory["queue"],
        "flags": inventory["flags"],
        "all_flags": inventory["all_flags"],
        "flag_reasons": inventory["flag_reasons"],
        "selected_flag_reason": inventory["selected_flag_reason"],
        "source_queue": selected_queue if view in SOURCE_REVIEW_VIEWS else [],
        "source_groups": inventory["source_groups"],
        "source_snapshot": source_snapshot,
        "finding_count": inventory["finding_count"],
        "review_counts": review_counts,
        "review_tabs": REVIEW_TABS,
        "total_review_count": len(
            {item.source_row.id for items in inventory["source_groups"].values() for item in items}
        )
        + len(inventory["queue"])
        + len(inventory["all_flags"]),
        "review_view": view,
        "review_view_label": review_view_label,
        **navigation,
        "next_nonempty_view": next_nonempty_view,
        "undo_record": undo_record,
        "profiles": get_profiles(db),
        "active_profile_id": get_active_profile_id(request, db),
        "can_bulk_accept_source": get_active_profile_role(request, db) == ROLE_ADMIN,
        "bulk_source_field_count": bulk_source_field_count,
        "bulk_source_skipped_count": bulk_source_skipped_count,
    }


@router.get("/ui/review")
def review_queue_ui(
    request: Request,
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
) -> RedirectResponse:
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(
        url=f"/ui/movies/health{query}#review-workbench",
        status_code=302,
    )


def _source_action_redirect(
    message: str,
    *,
    view: str = "differences",
    undo_decision: int | None = None,
) -> RedirectResponse:
    if view not in REVIEW_VIEWS:
        view = "differences"
    params = [f"view={quote(view)}", f"message={quote(message)}"]
    if undo_decision is not None:
        params.append(f"undo_decision={undo_decision}")
    return RedirectResponse(
        url=f"/ui/movies/health?{'&'.join(params)}#review-workbench",
        status_code=303,
    )


def _flag_action_redirect(message: str, *, flag_reason: str | None = None) -> RedirectResponse:
    params = ["view=flags", f"message={quote(message, safe='')}"]
    if flag_reason:
        params.append(f"flag_reason={quote(flag_reason, safe='')}")
    return RedirectResponse(
        url=f"/ui/movies/health?{'&'.join(params)}#review-workbench",
        status_code=303,
    )


@router.post("/ui/movies/health/review/source-row/{row_id}/field/{field_name}/{decision}")
def decide_source_review_field(
    row_id: int,
    field_name: str,
    decision: str,
    request: Request,
    view: str = "differences",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        result = decide_source_field(
            db,
            row_id=row_id,
            field_name=field_name,
            decision=decision,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    labels = {
        "use_source": "Source value applied",
        "keep_vault": "Vault value kept",
        "needs_research": "Sent to verification",
    }
    return _source_action_redirect(
        f"{labels[decision]} for {result.movie.vault_id or result.movie.title}.",
        view=view,
        undo_decision=result.id,
    )


@router.post("/ui/movies/health/review/source-accept-all")
def accept_all_source_review_differences(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        result = accept_all_source_differences(
            db,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect(
        (
            f"Applied {result.field_count} source values across "
            f"{result.movie_count} Vault entries from snapshot #{result.snapshot_id}."
            + (
                f" Left {result.skipped_field_count} conflicting source value in review."
                if result.skipped_field_count
                else ""
            )
        ),
        view="differences",
    )


@router.post("/ui/movies/health/review/source-row/{row_id}/defer")
def defer_source_review_movie(
    row_id: int,
    request: Request,
    view: str = "differences",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        records = defer_source_row_for_research(
            db,
            row_id=row_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    movie = records[0].movie
    return _source_action_redirect(
        f"{movie.vault_id or movie.title} moved to Needs Research. Showing the next movie.",
        view=view,
    )


@router.post("/ui/movies/health/review/source-decision/{decision_id}/undo")
def undo_source_review_field(
    decision_id: int,
    request: Request,
    view: str = "differences",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        result = undo_source_field_decision(
            db,
            decision_id=decision_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect(
        f"Decision undone for {result.movie.vault_id or result.movie.title}.",
        view=view,
    )


@router.post("/ui/movies/health/review/source-row/{row_id}/match/{movie_id}")
def confirm_source_row_match(
    row_id: int,
    movie_id: int,
    request: Request,
    view: str = "ambiguous",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        assign_source_row_match(
            db,
            row_id=row_id,
            movie_id=movie_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect(
        "Source row matched to the selected Vault entry.",
        view=view,
    )


@router.post("/ui/movies/health/review/source-row/{row_id}/create")
def create_source_row_movie(
    row_id: int,
    request: Request,
    view: str = "new",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        movie = create_movie_from_source_row(
            db,
            row_id=row_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect(f"{movie.vault_id} added to the Vault.", view=view)


@router.post("/ui/movies/health/review/source-row/{row_id}/dismiss-duplicate")
def dismiss_source_duplicate(
    row_id: int,
    view: str = "duplicates",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        dismiss_duplicate(db, row_id=row_id)
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect("Duplicate source row dismissed.", view=view)


def _load_movie(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@router.post("/ui/movies/health/review/flags/{movie_id}/resolve")
def resolve_flagged_queue_item(
    movie_id: int,
    flag_reason: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    movie = _load_movie(db, movie_id)
    if movie.flag is None:
        raise HTTPException(status_code=404, detail="Flag not found")
    clear_movie_flag(db, movie_id)
    db.commit()
    return _flag_action_redirect(
        f"{movie.vault_id or movie.title} removed from Flags.",
        flag_reason=flag_reason,
    )


def _selected_external_candidate(
    *,
    title: str,
    year: int | None,
    source: str,
    tmdb_id: int | None,
    imdb_id: str | None,
) -> dict:
    try:
        candidates = (
            lookup_movie_candidates(title, year, limit=20)
            if source == "tmdb"
            else lookup_omdb_candidates(title, year, limit=10)
        )
    except MovieLookupUnavailable as exc:
        raise HTTPException(status_code=503, detail="External lookup is not configured") from exc
    except MovieLookupNotFound as exc:
        raise HTTPException(status_code=404, detail="No provider matches found") from exc
    except MovieLookupError as exc:
        raise HTTPException(status_code=502, detail="External lookup failed") from exc

    candidate = next(
        (
            item
            for item in candidates
            if item.get("source") == source
            and (
                item.get("tmdb_id") == tmdb_id
                if source == "tmdb"
                else item.get("imdb_id") == imdb_id
            )
        ),
        None,
    )
    if candidate is None:
        raise HTTPException(
            status_code=400,
            detail="Selected match is not in the current provider results",
        )
    return candidate


def _ensure_external_ids_available(
    db: Session,
    *,
    movie_id: int,
    tmdb_id: int | None,
    imdb_id: str | None,
) -> None:
    if tmdb_id is not None:
        tmdb_owner = (
            db.query(Movie).filter(Movie.tmdb_id == tmdb_id, Movie.id != movie_id).one_or_none()
        )
        if tmdb_owner is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"TMDB {tmdb_id} is already assigned to "
                    f"{tmdb_owner.vault_id or tmdb_owner.title}"
                ),
            )
    if not imdb_id:
        return
    imdb_owner = (
        db.query(Movie).filter(Movie.imdb_id == imdb_id, Movie.id != movie_id).one_or_none()
    )
    if imdb_owner is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"IMDb {imdb_id} is already assigned to "
                f"{imdb_owner.vault_id or imdb_owner.title}"
            ),
        )


def _record_manual_match_provenance(
    db: Session,
    *,
    movie: Movie,
    candidate: dict,
) -> None:
    providers = []
    if candidate.get("tmdb_id"):
        providers.append(
            (
                "tmdb",
                str(candidate["tmdb_id"]),
                candidate.get("tmdb_payload_sha"),
                f"https://www.themoviedb.org/movie/{candidate['tmdb_id']}",
            )
        )
    if candidate.get("imdb_id"):
        providers.append(
            (
                "omdb",
                str(candidate["imdb_id"]),
                candidate.get("omdb_payload_sha"),
                f"https://www.imdb.com/title/{candidate['imdb_id']}/",
            )
        )
    for provider, provider_id, payload_sha, source_url in providers:
        record = (
            db.query(MovieIngestProvenance)
            .filter(
                MovieIngestProvenance.movie_id == movie.id,
                MovieIngestProvenance.provider == provider,
            )
            .one_or_none()
        )
        if record is None:
            record = MovieIngestProvenance(movie_id=movie.id, provider=provider)
            db.add(record)
        record.provider_id = provider_id
        record.payload_sha = payload_sha
        record.source_url = source_url
        record.notes = "Manually selected from the Flags review workbench."


@router.get(
    "/ui/movies/health/review/{movie_id}/matches",
    response_model=MovieLookupResponse,
)
def search_flagged_movie_matches(
    movie_id: int,
    title: str = Query(min_length=1, max_length=300),
    year: int | None = Query(default=None, ge=1870, le=2100),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
) -> MovieLookupResponse:
    movie = _load_movie(db, movie_id)
    if movie.flag is None:
        raise HTTPException(status_code=409, detail="Movie is not currently flagged")
    candidates = []
    provider_errors = 0
    for lookup, limit in (
        (lookup_movie_candidates, 10),
        (lookup_omdb_candidates, 10),
    ):
        try:
            candidates.extend(lookup(title.strip(), year, limit=limit))
        except (MovieLookupUnavailable, MovieLookupNotFound):
            continue
        except MovieLookupError:
            provider_errors += 1

    deduped = []
    seen = set()
    for candidate in candidates:
        key = (
            candidate.get("imdb_id")
            or (f"tmdb:{candidate.get('tmdb_id')}" if candidate.get("tmdb_id") else None)
            or (
                str(candidate.get("title") or "").casefold(),
                candidate.get("year"),
            )
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    if deduped:
        return MovieLookupResponse(items=deduped[:20])
    if provider_errors:
        raise HTTPException(status_code=502, detail="External lookup failed")
    raise HTTPException(status_code=404, detail="No provider matches found")


@router.post(
    "/ui/movies/health/review/{movie_id}/matches/apply",
    response_model=MovieMatchApplyResponse,
)
def apply_flagged_movie_match(
    movie_id: int,
    payload: MovieMatchSelection,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> MovieMatchApplyResponse:
    movie = _load_movie(db, movie_id)
    if movie.flag is None:
        raise HTTPException(status_code=409, detail="Movie is not currently flagged")

    candidate = _selected_external_candidate(
        title=payload.title.strip(),
        year=payload.year,
        source=payload.source,
        tmdb_id=payload.tmdb_id,
        imdb_id=payload.imdb_id,
    )
    imdb_id = candidate.get("imdb_id") or payload.imdb_id
    tmdb_id = candidate.get("tmdb_id") or payload.tmdb_id
    _ensure_external_ids_available(
        db,
        movie_id=movie.id,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
    )

    update_values = {
        "year": candidate.get("year"),
        "runtime": candidate.get("runtime"),
        "plot": candidate.get("synopsis") or candidate.get("overview"),
        "certificate": candidate.get("certificate"),
        "keywords": candidate.get("keywords"),
        "imdb_id": imdb_id,
        "tmdb_id": tmdb_id,
        "imdb_rating": candidate.get("imdb_rating"),
        "imdb_votes": candidate.get("imdb_votes"),
        "metascore": candidate.get("metascore"),
        "tomato_meter": candidate.get("tomato_meter"),
        "tomato_audience": candidate.get("tomato_audience"),
        "rt_score": candidate.get("rt_score"),
        "poster_url": candidate.get("poster_url"),
        "backdrop_url": candidate.get("backdrop_url"),
        "where_to_watch": candidate.get("where_to_watch"),
        "last_tmdb_fetch_at": candidate.get("last_tmdb_fetch_at"),
        "last_omdb_fetch_at": candidate.get("last_omdb_fetch_at"),
        "tmdb_payload_sha": candidate.get("tmdb_payload_sha"),
        "omdb_payload_sha": candidate.get("omdb_payload_sha"),
        "genres": candidate.get("genres"),
        "resolve_flag": True,
    }
    update_payload = MovieUpdate(
        **{key: value for key, value in update_values.items() if value not in (None, "", [])}
    )
    apply_movie_update(db, movie, update_payload)
    _record_manual_match_provenance(db, movie=movie, candidate=candidate)
    db.add(movie)
    db.commit()

    return MovieMatchApplyResponse(
        movie_id=movie.id,
        vault_id=movie.vault_id,
        title=movie.title,
        imdb_id=movie.imdb_id,
        tmdb_id=movie.tmdb_id,
        flag_resolved=movie.flag is None,
        message=f"{movie.vault_id or movie.title} matched and removed from Flags.",
    )


@router.post("/ui/movies/health/review/{movie_id}/checked")
def mark_review_checked(
    movie_id: int,
    request: Request,
    view: str = "vault",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    movie = _load_movie(db, movie_id)
    issues = detect_review_issues(movie)
    record_review_decision(
        db,
        movie=movie,
        issues=issues,
        decision="looks_right",
        profile_id=get_active_profile_id(request, db),
    )
    return _source_action_redirect(
        f"{movie.vault_id or movie.title} marked as checked.",
        view=view,
    )


@router.post("/ui/movies/health/review/{movie_id}/needs-fix")
def mark_review_needs_fix(
    movie_id: int,
    request: Request,
    view: str = "vault",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    movie = _load_movie(db, movie_id)
    issues = detect_review_issues(movie)
    if movie.flag is None:
        db.add(
            MovieFlag(
                movie_id=movie.id,
                reason="Human review",
                notes="; ".join(issue.label for issue in issues),
            )
        )
        db.flush()
    record_review_decision(
        db,
        movie=movie,
        issues=issues,
        decision="needs_fix",
        profile_id=get_active_profile_id(request, db),
    )
    return _source_action_redirect(
        f"{movie.vault_id or movie.title} added to Flags.",
        view=view,
    )


@router.post("/ui/movies/health/review/vault/needs-fix-all")
def mark_all_vault_reviews_needs_fix(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    result = mark_all_review_items_needs_fix(
        db,
        profile_id=get_active_profile_id(request, db),
    )
    return _source_action_redirect(
        (
            f"Moved {result.movie_count} Vault checks to Flags "
            f"with {result.finding_count} review findings."
        ),
        view="vault",
    )
