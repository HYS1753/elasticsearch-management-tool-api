# Backend API Architecture (`management_api`)

This document outlines the specific architectural guidelines, technology stack, and directory structure constraints for the Python Backend API. Agents and developers modifying the backend MUST adhere to these rules.

## 1. Technology Stack
- **Language:** Python 3.12+
- **Package Manager:** `uv`
- **Web Framework:** FastAPI
- **Data Validation:** Pydantic
- **Datastore Integrations:** Elasticsearch (primary target), MongoDB via Motor (if applicable for metadata).
- **Testing:** `pytest` (with `pytest-asyncio` and `pytest-mock`)

## 2. Directory Structure Constraints

The API strictly follows a **Domain-Driven Layered Architecture**. All application code resides within `src/python/elasticsearch/`. 

```text
management_api/
├── pyproject.toml         # Defines dependencies and pytest configurations
├── src/python/elasticsearch/
│   ├── application/       # Core application layers (MUST follow strict boundaries)
│   │   ├── endpoints/     # FastAPI routers and HTTP request/response handling.
│   │   ├── services/      # Core business logic. Called by endpoints.
│   │   ├── schemas/       # Pydantic DTOs for data validation.
│   │   └── repository/    # Data access logic (Elasticsearch/DB clients).
│   ├── config/            # Environment variables and application settings.
│   └── common/            # Enums, constants, exceptions, and shared utilities.
└── test/python/           # Test suite directory
```

## 3. Layered Architecture Rules

To maintain separation of concerns, the following interaction rules apply:

- **Endpoints (`application/endpoints/`)**
  - **Do:** Parse HTTP requests, validate via `schemas`, call a `service`, and return a formatted HTTP response.
  - **Don't:** Write business logic or direct database queries here.

- **Services (`application/services/`)**
  - **Do:** Contain the core business logic. Orchestrate calls to multiple `repository` functions if needed.
  - **Don't:** Depend on FastAPI `Request` objects or return HTTP Responses directly.

- **Schemas (`application/schemas/`)**
  - **Do:** Define Pydantic models for every Request and Response payload. Ensure type strictness.

- **Repository (`application/repository/`)**
  - **Do:** Isolate all external I/O (Elasticsearch queries, database calls). Return domain objects/dictionaries.
  - **Don't:** Contain business logic regarding *what* to do with the data, only *how* to fetch/store it.

## 4. Execution Protocol

- **Dependency Management:** Use `uv run` to execute commands in the isolated environment.
- **Testing:** 
  - Write unit tests mocking external clients (DB/Elasticsearch) in `test/python/unit/`.
  - Use pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`) as defined in `pyproject.toml`.
  - Command: `uv run pytest` (from the `management_api` directory).
