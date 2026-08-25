# Roadmap

## Phase 1: Django Foundation

- Django project and apps
- Custom user model with roles
- Template layout
- Static CSS
- Local SQLite database

## Phase 2: Authentication and Access

- Register
- Login
- Logout
- Protected views
- Role-based redirects and guards

## Phase 3: Queue Workflow

- Services model
- Counters model
- Tokens model
- Queue events model
- User token generation
- Staff call-next workflow
- Complete, skip, and cancel token actions

## Phase 4: Dashboards

- User dashboard
- Staff dashboard
- Admin dashboard
- Public/live queue display
- Empty states and feedback messages

## Phase 5: Search and Reporting

- Token number search
- User search
- Service filter
- Status filter
- Date filter
- Average waiting-time statistics

## Phase 6: Real-Time Updates

- Django Channels setup
- Websocket route
- Queue update broadcasts
- Live display refresh on updates
- Redis channel layer for production

## Phase 7: Deployment

- PostgreSQL database
- ASGI server using Daphne
- Redis for Channels
- Static file handling
- `DEBUG=False`
- Production `SECRET_KEY`
- Live URL
