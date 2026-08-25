# Smart Queue Management System

A digital queue management system for college offices, clinics, labs, help desks, and similar service points. Users take a virtual token, staff call the next person, and admins manage services, counters, staff assignments, and queue status.

## Core Features

- User registration, login, logout, and protected routes
- Role-based access for `USER`, `STAFF`, and `ADMIN`
- User dashboard with active token, queue position, and estimated wait time
- Service and counter/category management
- Digital queue token generation
- Live display of currently serving tokens
- Staff dashboard to call, complete, skip, or cancel tokens
- Queue history and average waiting-time statistics
- Admin controls for counters, services, staff, and queue status
- Search and filtering for tokens, users, history, services, and statuses
- Responsive UI for desktop, tablet, and mobile
- Loading, empty, and error states for all API-driven screens
- Real-time queue updates using Socket.IO or WebSockets

## Suggested Tech Stack

### Frontend

- React or Next.js
- TypeScript
- Tailwind CSS or CSS modules
- Socket.IO client

### Backend

- Node.js with Express or NestJS
- TypeScript
- JWT authentication
- bcrypt password hashing
- Socket.IO

### Database

- PostgreSQL with Prisma ORM
- Alternative: MongoDB with Mongoose

### Deployment

- Frontend: Vercel or Netlify
- Backend: Render, Railway, or Fly.io
- Database: Neon, Supabase, or Railway PostgreSQL

## Roles

### USER

- Register and log in
- View available services
- Take a virtual queue token
- Track active token status
- View current queue position
- View estimated waiting time
- View personal queue history

### STAFF

- Access staff dashboard
- View assigned counter or service
- Call the next waiting token
- Mark tokens as completed, skipped, or cancelled
- See currently serving token

### ADMIN

- Manage users and roles
- Create, edit, and disable services
- Create, edit, and disable counters
- Assign staff to counters
- Open or close queues
- View history and statistics

## Main Screens

1. Authentication
   - Register
   - Login
   - Logout
   - Protected route handling

2. User Dashboard
   - Active token
   - Queue position
   - Estimated wait time
   - Available services
   - Recent queue activity

3. Take Token
   - Select service
   - Generate token
   - Show token number, service, timestamp, and status

4. Live Queue Display
   - Currently serving token per counter
   - Next waiting tokens
   - Real-time updates

5. Staff Dashboard
   - Current token
   - Waiting queue
   - Call next
   - Complete, skip, or cancel token

6. Admin Dashboard
   - Total tokens today
   - Active counters
   - Open services
   - Average waiting time
   - Queue status summary

7. Admin Management
   - Services
   - Counters
   - Staff assignments
   - Queue history
   - User management

## Database Design

### users

| Field | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| name | String | User full name |
| email | String | Unique |
| passwordHash | String | Hashed password |
| role | Enum | USER, STAFF, ADMIN |
| createdAt | DateTime | Account creation time |

### services

| Field | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| name | String | Service name |
| description | String | Optional details |
| isActive | Boolean | Whether users can take tokens |
| createdAt | DateTime | Creation time |

### counters

| Field | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| name | String | Counter name |
| serviceId | UUID | Related service |
| staffId | UUID | Assigned staff member |
| status | Enum | OPEN, CLOSED, PAUSED |

### tokens

| Field | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| tokenNumber | String | Human-readable token |
| userId | UUID | Token owner |
| serviceId | UUID | Requested service |
| counterId | UUID | Assigned counter, if any |
| status | Enum | WAITING, SERVING, COMPLETED, SKIPPED, CANCELLED |
| createdAt | DateTime | Token creation time |
| calledAt | DateTime | When staff called the token |
| completedAt | DateTime | When token was completed |

### queue_events

| Field | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| tokenId | UUID | Related token |
| action | String | CREATED, CALLED, COMPLETED, SKIPPED, CANCELLED |
| performedBy | UUID | User/staff/admin who performed action |
| timestamp | DateTime | Event time |

## API Endpoints

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Services

- `GET /api/services`
- `POST /api/services`
- `PATCH /api/services/:id`
- `DELETE /api/services/:id`

### Counters

- `GET /api/counters`
- `POST /api/counters`
- `PATCH /api/counters/:id`
- `DELETE /api/counters/:id`

### Tokens

- `POST /api/tokens`
- `GET /api/tokens/my`
- `GET /api/tokens/live`
- `PATCH /api/tokens/:id/call`
- `PATCH /api/tokens/:id/complete`
- `PATCH /api/tokens/:id/skip`
- `PATCH /api/tokens/:id/cancel`

### Statistics

- `GET /api/stats/overview`
- `GET /api/stats/wait-times`
- `GET /api/stats/history`

## Real-Time Events

### Server Emits

- `token_created`
- `token_called`
- `token_completed`
- `token_skipped`
- `token_cancelled`
- `queue_updated`
- `counter_status_changed`

### Clients Update

- User dashboard
- Staff dashboard
- Admin dashboard
- Public live queue display

## Search and Filtering

- Search token by token number
- Filter tokens by status
- Filter queue history by date range
- Filter history by service
- Search users by name or email
- Filter counters by status

## Required UI States

Every API-driven page should include:

- Loading state
- Empty state
- Error state
- Success feedback
- Disabled controls while submitting
- Responsive layouts for desktop, tablet, and mobile

## Suggested Repository Structure

```text
smart-queue-management-system/
├── client/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── styles/
│   └── package.json
├── server/
│   ├── src/
│   │   ├── config/
│   │   ├── controllers/
│   │   ├── middleware/
│   │   ├── models/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── sockets/
│   │   └── utils/
│   └── package.json
├── docs/
│   ├── API.md
│   ├── DATABASE.md
│   └── ROADMAP.md
└── README.md
```

## Development Milestones

1. Set up frontend, backend, database, and environment variables.
2. Implement authentication and protected routes.
3. Add role-based access control.
4. Create database models and relationships.
5. Build user dashboard and token generation flow.
6. Build live queue display.
7. Build staff dashboard and call-next logic.
8. Add Socket.IO real-time updates.
9. Build admin service and counter management.
10. Add queue history, search, filters, and waiting-time statistics.
11. Add loading, empty, and error states across the app.
12. Test desktop, tablet, and mobile responsiveness.
13. Deploy frontend, backend, and database.

## Demo Credentials

Use demo credentials only in development or seeded demo deployments.

```text
Admin: admin@example.com / Admin@123
Staff: staff@example.com / Staff@123
User: user@example.com / User@123
```

## License

MIT
