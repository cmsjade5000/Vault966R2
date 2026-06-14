# Vault 966 Performance Benchmark

Date: June 13, 2026

## Method

- Target: managed Vault service at `http://127.0.0.1:8000`
- Database: SQLite with WAL, foreign keys, 15-second busy timeout, and
  `synchronous=NORMAL`
- Authentication: local signed session established through `POST /login`
- Warm-up: 5 requests per route
- Sequential sample: 10 requests
- Concurrent sample: 12 requests with 4 workers
- Client timeout: 15 seconds
- A response counts as successful only when it returns HTTP 200

## Results

| Route | Sequential median | Sequential p95 | 4-worker median | 4-worker p95 | Failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/health` | 1.86 ms | 2.13 ms | 3.85 ms | 5.23 ms | 0 |
| `/login?unlocked=1` | 11.71 ms | 12.30 ms | 36.41 ms | 54.49 ms | 0 |
| `/ui/movies?page=1` | 1,514.24 ms | 1,568.42 ms | 9,280.45 ms | 9,691.27 ms | 0 |
| `/ui/movies/1` | 1,663.94 ms | 1,713.08 ms | 9,749.59 ms | 10,084.78 ms | 0 |

## Findings

- Health and login routes are responsive and remained reliable under four-way
  concurrency.
- Database-backed library and movie detail pages are the primary performance
  bottlenecks.
- The final bounded run had no request failures.
- An exploratory eight-worker run exceeded a 30-second client timeout on the
  library route and left the single service process draining queued work. This
  indicates poor scalability under sustained concurrent page rendering.

This report is the first recorded benchmark for the current configuration. It
does not establish improvement versus the pre-WAL implementation; use these
numbers as the baseline for the next optimization pass.

## Optimization Results

The following changes were applied after the baseline:

- Batched source field decision loading, replacing one query per matched source
  row with one query per review queue build.
- Scoped trust checks to only the movie IDs rendered by the library or detail
  page.
- Removed daily spotlight collection reconstruction from ordinary detail views.
  Spotlight links already pass the explicit `spotlight=1` context.

The same benchmark method was then repeated:

| Route | Baseline sequential median | Optimized sequential median | Baseline 4-worker median | Optimized 4-worker median |
| --- | ---: | ---: | ---: | ---: |
| `/ui/movies?page=1` | 1,514.24 ms | 60.94 ms | 9,280.45 ms | 254.87 ms |
| `/ui/movies/1` | 1,663.94 ms | 96.03 ms | 9,749.59 ms | 672.38 ms |

- Library sequential median latency decreased by 96.0%.
- Library four-worker median latency decreased by 97.3%.
- Movie detail sequential median latency decreased by 94.2%.
- Movie detail four-worker median latency decreased by 93.1%.
- The optimized benchmark completed with zero failures.
