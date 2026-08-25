# Django Routes and API Plan

This version is a Django server-rendered application with regular routes and templates. JSON API endpoints can be added later with Django REST Framework if the project needs a separate frontend or mobile app.

## Current Routes

### Authentication

| Method | URL | Role | Description |
| --- | --- | --- | --- |
| GET, POST | `/accounts/register/` | Public | Create a new `USER` account |
| GET, POST | `/accounts/login/` | Public | Log in |
| POST | `/accounts/logout/` | Authenticated | Log out |

### Dashboards

| Method | URL | Role | Description |
| --- | --- | --- | --- |
| GET | `/` | Authenticated | Role-aware dashboard redirect/render |
| GET | `/staff/` | STAFF, ADMIN | Staff queue workflow |
| GET | `/manage/` | ADMIN | Admin overview |

### Queue

| Method | URL | Role | Description |
| --- | --- | --- | --- |
| GET, POST | `/queue/take-token/` | USER | Select service and generate token |
| GET | `/queue/live/` | Authenticated | Live queue display |
| GET | `/queue/history/` | STAFF, ADMIN | Searchable and filterable history |
| POST | `/queue/staff/call-next/` | STAFF, ADMIN | Call next waiting token |
| GET | `/queue/staff/token/<id>/<action>/` | STAFF, ADMIN | Complete, skip, or cancel token |

### Admin

| Method | URL | Role | Description |
| --- | --- | --- | --- |
| GET, POST | `/admin/` | Django staff/superuser | Manage users, services, counters, tokens, and events |

## Websocket

Endpoint:

```text
/ws/queue/
```

## Real-Time Events

The server broadcasts queue updates through Django Channels.

| Event | Description |
| --- | --- |
| `token_created` | A user generated a token |
| `token_called` | Staff called a token |
| `token_completed` | Staff completed a token |
| `token_skipped` | Staff skipped a token |
| `token_cancelled` | Token was cancelled |

## Future JSON API

Suggested Django REST Framework endpoints:

### Auth

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`

### Services

- `GET /api/services/`
- `POST /api/services/`
- `PATCH /api/services/<id>/`
- `DELETE /api/services/<id>/`

### Counters

- `GET /api/counters/`
- `POST /api/counters/`
- `PATCH /api/counters/<id>/`
- `DELETE /api/counters/<id>/`

### Tokens

- `POST /api/tokens/`
- `GET /api/tokens/my/`
- `GET /api/tokens/live/`
- `PATCH /api/tokens/<id>/call/`
- `PATCH /api/tokens/<id>/complete/`
- `PATCH /api/tokens/<id>/skip/`
- `PATCH /api/tokens/<id>/cancel/`

### Statistics

- `GET /api/stats/overview/`
- `GET /api/stats/wait-times/`
- `GET /api/stats/history/`
