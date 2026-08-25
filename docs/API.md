# API Plan

Base path: `/api`

## Authentication

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| POST | `/auth/register` | Public | Create a user account |
| POST | `/auth/login` | Public | Log in and receive an auth token |
| POST | `/auth/logout` | Authenticated | Log out |
| GET | `/auth/me` | Authenticated | Get current user profile |

## Services

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| GET | `/services` | Authenticated | List active services |
| POST | `/services` | ADMIN | Create a service |
| PATCH | `/services/:id` | ADMIN | Update a service |
| DELETE | `/services/:id` | ADMIN | Disable or delete a service |

## Counters

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| GET | `/counters` | STAFF, ADMIN | List counters |
| POST | `/counters` | ADMIN | Create a counter |
| PATCH | `/counters/:id` | ADMIN | Update a counter |
| DELETE | `/counters/:id` | ADMIN | Disable or delete a counter |

## Tokens

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| POST | `/tokens` | USER | Generate a queue token |
| GET | `/tokens/my` | USER | List current user's tokens |
| GET | `/tokens/live` | Authenticated | Get live queue state |
| PATCH | `/tokens/:id/call` | STAFF, ADMIN | Call a waiting token |
| PATCH | `/tokens/:id/complete` | STAFF, ADMIN | Complete a token |
| PATCH | `/tokens/:id/skip` | STAFF, ADMIN | Skip a token |
| PATCH | `/tokens/:id/cancel` | USER, STAFF, ADMIN | Cancel a token |

## Statistics

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| GET | `/stats/overview` | ADMIN | Dashboard overview stats |
| GET | `/stats/wait-times` | STAFF, ADMIN | Average waiting-time stats |
| GET | `/stats/history` | STAFF, ADMIN | Queue history with filters |

## Real-Time Events

Socket.IO namespace: `/queue`

### Client Emits

| Event | Sent By | Description |
| --- | --- | --- |
| `join_queue_room` | Authenticated users | Subscribe to service/counter updates |
| `leave_queue_room` | Authenticated users | Unsubscribe from updates |

### Server Emits

| Event | Description |
| --- | --- |
| `token_created` | A user generated a token |
| `token_called` | Staff called a token |
| `token_completed` | Staff completed a token |
| `token_skipped` | Staff skipped a token |
| `token_cancelled` | A token was cancelled |
| `queue_updated` | Queue order or counts changed |
| `counter_status_changed` | Counter status changed |
