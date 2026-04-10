---
name: backend-dev
description: Build and maintain backend services with FastAPI, Pydantic, async endpoints, and PostgreSQL-style data access. Use when Codex needs to create, modify, or review backend API code, routing, validation, service logic, models, or database integration in the backend scope.
---

# Backend Dev

## Instrucciones

- Use FastAPI for HTTP APIs.
- Use Pydantic models for request and response validation.
- Prefer clear separation between `routers/`, `services/`, and `models/`.
- Use async functions when the project architecture supports them.
- Keep endpoint handlers thin and move business logic into services.
- Handle validation and error responses explicitly.

## Tareas

- Create or update REST endpoints.
- Validate incoming and outgoing data.
- Connect backend flows to PostgreSQL or equivalent persistence layers.
- Implement service logic and error handling.
- Review backend changes for regressions in API behavior.
