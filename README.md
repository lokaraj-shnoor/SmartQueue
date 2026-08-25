# Smart Queue Management System

A Django and Python based digital queue management system for college offices, clinics, labs, help desks, and similar service points. Users take a virtual token instead of physically waiting in line, staff call the next token, and admins manage services, counters, users, and queue status.

## Features

- Register, login, logout, and protected routes
- Role-based access for `USER`, `STAFF`, and `ADMIN`
- User dashboard with active token, queue position, available services, and recent history
- Staff dashboard to call the next person, complete tokens, and skip tokens
- Admin dashboard with queue totals and links to Django Admin controls
- Service and counter database relationships
- Digital queue token generation
- Live queue display with Django Channels websocket updates
- Queue history with token search, service filter, status filter, and date filter
- Average waiting-time calculation
- Loading-safe, empty-state, and message-based feedback patterns
- Responsive UI for desktop, tablet, and mobile

## Tech Stack

- Python 3.11+
- Django 5
- Django Channels
- Daphne ASGI server
- SQLite for local development
- PostgreSQL recommended for deployment
- HTML templates and responsive CSS

## Project Structure

```text
smart-queue-management-system/
├── accounts/
├── config/
├── dashboard/
├── queues/
├── static/
├── templates/
├── docs/
├── manage.py
├── requirements.txt
└── README.md
```

## Local Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create database tables:

```powershell
python manage.py makemigrations
python manage.py migrate
```

Create an admin user:

```powershell
python manage.py createsuperuser
```

Run the development server:

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Roles

### USER

- Register and log in
- View services
- Take a virtual token
- Track active token status
- View queue position
- View recent token history

### STAFF

- Access staff dashboard
- View assigned open counter
- Call next waiting token
- Complete or skip current token
- View waiting queue

### ADMIN

- Access admin dashboard
- Manage users, roles, services, counters, tokens, and queue events through Django Admin
- View queue history and statistics
- Call and manage tokens when needed

## Main URLs

| URL | Purpose |
| --- | --- |
| `/` | Role-aware dashboard |
| `/accounts/register/` | Register |
| `/accounts/login/` | Login |
| `/accounts/logout/` | Logout |
| `/queue/take-token/` | Generate user token |
| `/queue/live/` | Live queue display |
| `/staff/` | Staff dashboard |
| `/manage/` | Admin dashboard |
| `/queue/history/` | Searchable queue history |
| `/admin/` | Django Admin |

## Real-Time Updates

The app uses Django Channels.

Websocket endpoint:

```text
/ws/queue/
```

Broadcast events:

- `token_created`
- `token_called`
- `token_completed`
- `token_skipped`
- `token_cancelled`

The current development setup uses `InMemoryChannelLayer`. For production, replace it with Redis.

## GitHub Repository

Remote repository:

[https://github.com/lokaraj-shnoor/smart-queue-management-system](https://github.com/lokaraj-shnoor/smart-queue-management-system)

Push local changes:

```powershell
git remote add origin https://github.com/lokaraj-shnoor/smart-queue-management-system.git
git push -u origin main
```

If `origin` already exists:

```powershell
git remote set-url origin https://github.com/lokaraj-shnoor/smart-queue-management-system.git
git push -u origin main
```

## Deployment Notes

For deployment, use:

- PostgreSQL database
- Redis channel layer
- Daphne or another ASGI-compatible server
- `DEBUG=False`
- Strong `SECRET_KEY`
- Proper `ALLOWED_HOSTS`
- Static file hosting via WhiteNoise, S3, or platform static handling

## License

MIT
