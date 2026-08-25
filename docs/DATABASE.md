# Database Plan

The current implementation uses Django ORM models. SQLite is configured for local development, and PostgreSQL is recommended for deployment.

## Entity Relationships

- One user can have many tokens.
- One service can have many counters.
- One service can have many tokens.
- One counter can serve many tokens.
- One staff user can be assigned to many counters.
- One token can have many queue events.

## Models

### accounts.User

Extends Django `AbstractUser`.

Fields:

- `username`
- `email`
- `password`
- `first_name`
- `last_name`
- `role`

Roles:

- `USER`
- `STAFF`
- `ADMIN`

### queues.Service

Fields:

- `name`
- `description`
- `is_active`
- `created_at`
- `updated_at`

### queues.Counter

Fields:

- `name`
- `service`
- `staff`
- `status`
- `created_at`
- `updated_at`

Statuses:

- `OPEN`
- `CLOSED`
- `PAUSED`

### queues.Token

Fields:

- `token_number`
- `user`
- `service`
- `counter`
- `status`
- `created_at`
- `called_at`
- `completed_at`

Statuses:

- `WAITING`
- `SERVING`
- `COMPLETED`
- `SKIPPED`
- `CANCELLED`

### queues.QueueEvent

Fields:

- `token`
- `action`
- `performed_by`
- `timestamp`

Actions:

- `CREATED`
- `CALLED`
- `COMPLETED`
- `SKIPPED`
- `CANCELLED`

## Statistics

Average waiting time:

```text
called_at - created_at
```

Average service time:

```text
completed_at - called_at
```

## Production Recommendation

Use PostgreSQL in production. Update environment variables and install a PostgreSQL driver such as `psycopg`.
