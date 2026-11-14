# AutoSemilla API

Status: the data API is generated automatically by Supabase from the `experiments` and `notes` tables. The Python engine and notebooks do not call it yet. No custom endpoints (edge functions or HTTP servers) exist.

## Overview

| Item | Value |
|---|---|
| Base URL | `$SUPABASE_URL/rest/v1` |
| Protocol | HTTPS, JSON |
| Authentication | Anon API key (no user login) |
| Versioning | None; changes are made through database migrations |

## Authentication

Every request sends the anon key in two headers:

```
apikey: $SUPABASE_ANON_KEY
Authorization: Bearer $SUPABASE_ANON_KEY
```

There is no sign-in. Anyone holding the anon key can read, create, update and delete rows in both tables. Row level security is enabled but its policies are intentionally open (`USING (true)`).

## Common headers

| Header | When | Purpose |
|---|---|---|
| `Content-Type: application/json` | POST, PATCH | Body format |
| `Prefer: return=representation` | POST, PATCH | Return the affected rows |
| `Prefer: return=minimal` | POST, PATCH, DELETE | Return an empty body |
| `Prefer: resolution=merge-duplicates` | POST | Upsert on primary key |
| `Prefer: count=exact` | GET | Add a total count in the `Content-Range` header |

## Filtering and sorting (query string)

| Operator | Example | Meaning |
|---|---|---|
| `eq` | `benchmark=eq.invsqrt` | Equals |
| `neq` | `promotion=neq.rejected` | Not equal |
| `gt`, `gte`, `lt`, `lte` | `cheap_score=gte.40` | Comparisons |
| `in` | `benchmark=in.(dqi,dfthcsos)` | One of a list |
| `is` | `ranking_value=is.null` | Null checks |
| `order` | `order=ranking_value.desc.nullslast` | Sorting |
| `limit`, `offset` | `limit=10&offset=20` | Pagination |
| `select` | `select=seed_id,cheap_score` | Choose columns |

## Resource: experiments

One row per candidate tested by the engine.

Primary key: `seed_id` (text).

| Field | Type | Required | Notes |
|---|---|---|---|
| `seed_id` | text | yes | Deterministic 20-character hex ID |
| `seed` | object (jsonb) | yes | Full seed: benchmark, strategy, params, seed, generation, parent_id |
| `benchmark` | text | yes | `invsqrt`, `dqi` or `dfthcsos` |
| `strategy` | text | yes | `explore` or `exploit` |
| `valid` | boolean | yes | Passed the schema and range checks |
| `cheap_score` | number | yes | Proxy score. Not the official competition score |
| `features` | object | no | Default `{}` |
| `reasons` | array | no | Default `[]`; reasons for invalidity |
| `elapsed_ms` | number | yes | Evaluation time |
| `promotion` | text | no | `candidate` (default), `promoted`, `compiled`, `verified`, `rejected` |
| `outcome` | object | no | Official verifier result, if any |
| `ranking_value` | number | no | Official metric, higher is better; only when verified |
| `official_verified` | boolean | no | Default `false` |
| `created_at` | timestamp | no | Set by the server |

### List experiments

```bash
curl "$SUPABASE_URL/rest/v1/experiments?benchmark=eq.invsqrt&order=cheap_score.desc&limit=5&select=seed_id,cheap_score,promotion" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

Response `200 OK`:

```json
[
  { "seed_id": "9af9633639d03232d2ab", "cheap_score": 83.38, "promotion": "promoted" },
  { "seed_id": "8531f7c74aadd916b40c", "cheap_score": 66.5, "promotion": "promoted" }
]
```

### Get the best officially verified experiments

```bash
curl "$SUPABASE_URL/rest/v1/experiments?benchmark=eq.dqi&official_verified=eq.true&order=ranking_value.desc&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

### Create an experiment

```bash
curl -X POST "$SUPABASE_URL/rest/v1/experiments" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{
    "seed_id": "c510e8a0f3590a4e7539",
    "seed": {"benchmark": "invsqrt", "strategy": "explore", "params": {"bits": 64, "precision": 32, "ancilla": 4, "layers": 4}, "seed": 7, "generation": 1, "parent_id": null},
    "benchmark": "invsqrt",
    "strategy": "explore",
    "valid": true,
    "cheap_score": 41.6,
    "features": {"bits": 64, "precision": 32},
    "reasons": [],
    "elapsed_ms": 0.12
  }'
```

Response `201 Created`: the created row as a JSON array.

### Update an experiment (record an official verification)

```bash
curl -X PATCH "$SUPABASE_URL/rest/v1/experiments?seed_id=eq.c510e8a0f3590a4e7539" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"promotion": "verified", "official_verified": true, "ranking_value": 123.4, "outcome": {"verifier_status": "PASS"}}'
```

Response `200 OK`: the updated rows. Always include a filter; a PATCH without one is rejected.

### Delete an experiment

```bash
curl -X DELETE "$SUPABASE_URL/rest/v1/experiments?seed_id=eq.c510e8a0f3590a4e7539" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Prefer: return=minimal"
```

Response `204 No Content`. Deleting removes data permanently; confirm before doing it.

## Resource: notes

Short observations recorded by the engine.

Primary key: `note_id` (text, a SHA-256 hash of kind, body and source).

| Field | Type | Required | Notes |
|---|---|---|---|
| `note_id` | text | yes | Unique hash; duplicates are rejected |
| `kind` | text | yes | Category of the note |
| `body` | text | yes | Note text |
| `source_hash` | text | no | Default empty string |
| `created_at` | timestamp | no | Set by the server |

### Create a note

```bash
curl -X POST "$SUPABASE_URL/rest/v1/notes" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"note_id": "e3b0c44298fc1c149afbf4c8996fb924", "kind": "run", "body": "Batch of 64 invsqrt candidates completed", "source_hash": ""}'
```

### List notes, newest first

```bash
curl "$SUPABASE_URL/rest/v1/notes?order=created_at.desc&limit=20" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

## Errors

Errors return a JSON body with `code`, `message`, `details` and `hint`:

```json
{ "code": "23505", "details": "Key (seed_id)=(c510e8a0f3590a4e7539) already exists.", "hint": null, "message": "duplicate key value violates unique constraint \"experiments_pkey\"" }
```

| Status | Meaning | Typical cause |
|---|---|---|
| 200 | OK | Successful read or update |
| 201 | Created | Successful insert with `return=representation` |
| 204 | No Content | Successful delete or minimal write |
| 400 | Bad Request | Invalid filter or value, or a check constraint failed (e.g. unknown `benchmark` or `promotion`) |
| 401 | Unauthorized | Missing or invalid anon key |
| 403 | Forbidden | Role lacks permission on the table |
| 404 | Not Found | Table or endpoint does not exist |
| 409 | Conflict | Duplicate `seed_id` or `note_id` |
| 500 | Server Error | Unexpected failure; retry later and check the Supabase dashboard logs |

Client guidance: treat 409 on insert as "already stored" and skip it; retry 500 with backoff; never retry 400 without changing the request.

## Template for new endpoints

Copy this section for each new endpoint.

### `METHOD /path`

- **Purpose:** one sentence on what it does.
- **Authentication:** none / anon key / signed-in user (`Authorization: Bearer <access token>`).
- **Path and query parameters:** name, type, required, description.
- **Request body:** JSON schema or field table.
- **Success response:** status code and example body.
- **Errors:** status codes specific to this endpoint.
- **Example:** a runnable `curl` command.

## Recommended tools

- **Supabase data API:** the root `$SUPABASE_URL/rest/v1/` returns an OpenAPI description of all tables when called with the anon key. Import it into Swagger UI, Scalar or Redocly to browse and test interactively.
- **Redocly CLI or Scalar:** render an OpenAPI file into a polished, searchable HTML site, including custom endpoints added later.
- **OpenAPI with Hono and Zod (for edge functions):** describe each route in code and generate the spec automatically, so docs cannot drift from the implementation.
- **Python docs (for the engine):** `pdoc` generates HTML reference pages straight from the docstrings in `autosemilla/`, with no extra setup.
- **Bruno or Postman:** share runnable collections of the examples above with collaborators.
