# Database Plan

No custom database models are implemented in today's scaffold.

Planned models for the next phase:

## User Roles

Use Django users with role support:

- `USER`
- `STAFF`
- `ADMIN`

## Service

Planned fields:

- `name`
- `description`
- `is_active`
- `created_at`
- `updated_at`

## Counter

Planned fields:

- `name`
- `service`
- `staff`
- `status`
- `created_at`
- `updated_at`

## Token

Planned fields:

- `token_number`
- `user`
- `service`
- `counter`
- `status`
- `created_at`
- `called_at`
- `completed_at`

## QueueEvent

Planned fields:

- `token`
- `action`
- `performed_by`
- `timestamp`
