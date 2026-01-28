# Repository Guidelines

## Project Structure & Module Organization
- `web/`: Vue 3 + Vite frontend (UI, routing, state).
- `nexus/`: FastAPI service and LangChain pipeline logic.
- `api/`: Spring Boot backend API (Java 17).
- `docs/`: Documentation and design notes.
- `README.md`: Product overview and workflow specifications.

## Build, Test, and Development Commands
Frontend (`web/`):
- `npm install`: Install UI dependencies.
- `npm run dev`: Start Vite dev server.
- `npm run build`: Type-check (`vue-tsc`) and build static assets.
- `npm run preview`: Preview production build locally.

Python service (`nexus/`):
- `pip install -r requirements.txt`: Install backend deps.
- `uvicorn nexus.main:create_app --reload`: Run FastAPI locally.
- `pytest`: Run Python tests (if present).

Java API (`api/`):
- `mvn spring-boot:run`: Start Spring Boot service.
- `mvn test`: Run unit tests.
- `mvn package`: Build JAR.

## Coding Style & Naming Conventions
- Follow existing language defaults: TypeScript/Vue in `web/`, Python in `nexus/`, Java in `api/`.
- Prefer 2-space indentation in Vue/TypeScript files, 4 spaces in Python, and standard Java formatting.
- File naming: `camelCase` for TS/JS files, `snake_case` for Python modules, `PascalCase` for Java classes.
- Formatting tools in dependencies: `black` and `isort` are available for Python.

## Testing Guidelines
- Python: `pytest` (no explicit coverage config detected).
- Java: Spring Boot test starter via Maven.
- Frontend: no test runner configured; add tests only if introducing one.
- Name tests following framework defaults (e.g., `test_*.py`, `*Test.java`).

## Commit & Pull Request Guidelines
- Git history is unavailable in this workspace; use clear, imperative commit messages (e.g., “Add API retry logic”).
- PRs should include: brief summary, testing notes, and screenshots for UI changes.
- Link related issues/tickets when available.

## Configuration Tips
- Frontend expects `VITE_API_BASE_URL` and `VITE_NEXUS_URL` (see `web/vite.config.ts`).
- Keep secrets in `.env` files and exclude them from commits.
