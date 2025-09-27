# Next.js Frontend Delivery Plan

## 1. Project bootstrap & tooling
- [ ] Create a new `frontend/` workspace managed with pnpm or npm, alongside the FastAPI backend.
- [ ] Initialize the app with `npx create-next-app@latest` (TypeScript template) and configure the package manager to match the repo convention (`package.json` already exists for the legacy client, so add a workspace entry if switching to pnpm).
- [ ] Add base linting and formatting (ESLint, Prettier) and align rules with the backend repo (e.g., use the shared `.editorconfig`).
- [ ] Configure absolute import aliases (e.g., `@/components`, `@/lib`) and establish a shared types folder for API responses that mirrors Pydantic schemas.

## 2. Environment wiring & data access
- [ ] Decide on runtime vs. build-time configuration. Use `.env.local` for API base URL and expose it via `NEXT_PUBLIC_API_BASE_URL`.
- [ ] Add an API client layer (e.g., Axios or fetch wrappers) with typed helpers for:
  - `/movies/search`
  - `/movies/{id}/detail`
  - `/movies/picks`
  - `/fliclists` CRUD endpoints
- [ ] Implement error handling hooks/utilities (e.g., SWR `useSWR` or React Query) and global loading/error UI patterns.
- [ ] Ensure CORS and authentication considerations are solved by verifying `api/main.py` configuration or adding tokens if needed.

## 3. Routing & page structure
- [ ] Use the Next.js App Router (preferred) to create parallel routes matching existing FastAPI UI:
  - `/movies` – list/grid view with filters
  - `/movies/[id]` – detail page
  - `/fliclists` – saved preset management
- [ ] Set up shared layout with navigation, theme, and global providers (state management, SWR, etc.).
- [ ] Add metadata and SEO configuration mirroring current meta tags.

## 4. UI implementation
- [ ] Recreate the movies grid using reusable components (`MovieCard`, `MovieGrid`, `FilterSidebar`).
- [ ] Port current Jinja filters (genre, service, year, etc.) into controlled React components with synchronized query parameters.
- [ ] Implement detail view showing synopsis, services, trailers, and the new Flic score breakdown once available.
- [ ] Build Fliclist CRUD UI (list, create form, rename/update when backend work completes) with optimistic updates.
- [ ] Incorporate responsive design; ensure mobile breakpoints match existing CSS/figma references if available.

## 5. State management & UX enhancements
- [ ] Decide between server components + client hooks, or client-heavy approach using React Query for caching.
- [ ] Persist last-used filters in local storage or query parameters to match current UX.
- [ ] Surface loading skeletons and empty states for searches with no results.

## 6. Testing & quality
- [ ] Configure unit testing with Vitest/Jest and React Testing Library for components.
- [ ] Add integration tests for critical flows (filtering, viewing details, managing Fliclists).
- [ ] Set up Playwright or Cypress end-to-end tests hitting the FastAPI backend (perhaps via docker-compose).
- [ ] Integrate lint/test commands into existing CI (GitHub Actions or similar) alongside backend checks.

## 7. Deployment & integration
- [ ] Decide on deployment target (Vercel for Next.js or containerized within existing infra).
- [ ] Update Docker compose / infrastructure scripts to build and serve the Next.js app (either standalone or behind the FastAPI server).
- [ ] Adjust FastAPI UI routes (`api/routers/ui`) to redirect to the Next.js frontend once feature parity is achieved.
- [ ] Document setup instructions in `README.md` (how to run backend + frontend together, environment variables, scripts).

## 8. Migration & cutover
- [ ] Run internal QA to compare Jinja UI against the new Next.js implementation.
- [ ] Plan a staged rollout: deploy Next.js under `/app` or feature flag before replacing `/` routes.
- [ ] Remove obsolete Jinja templates and server-side routes after successful launch.
