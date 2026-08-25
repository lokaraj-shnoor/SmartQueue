# Database Plan

Recommended database: PostgreSQL.

Recommended ORM: Prisma.

## Entity Relationships

- One user can have many tokens.
- One service can have many counters.
- One service can have many tokens.
- One counter can serve many tokens.
- One token can have many queue events.
- One staff user can be assigned to one or more counters, depending on project scope.

## Tables

### users

- `id`
- `name`
- `email`
- `passwordHash`
- `role`
- `createdAt`
- `updatedAt`

### services

- `id`
- `name`
- `description`
- `isActive`
- `createdAt`
- `updatedAt`

### counters

- `id`
- `name`
- `serviceId`
- `staffId`
- `status`
- `createdAt`
- `updatedAt`

### tokens

- `id`
- `tokenNumber`
- `userId`
- `serviceId`
- `counterId`
- `status`
- `createdAt`
- `calledAt`
- `completedAt`

### queue_events

- `id`
- `tokenId`
- `action`
- `performedBy`
- `timestamp`

## Enums

### Role

- `USER`
- `STAFF`
- `ADMIN`

### CounterStatus

- `OPEN`
- `CLOSED`
- `PAUSED`

### TokenStatus

- `WAITING`
- `SERVING`
- `COMPLETED`
- `SKIPPED`
- `CANCELLED`

## Statistics

Average waiting time can be calculated from:

```text
calledAt - createdAt
```

Average service time can be calculated from:

```text
completedAt - calledAt
```
