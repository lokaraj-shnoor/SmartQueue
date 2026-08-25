# Smart Queue Management System

Django and Python scaffold for a Smart Queue Management System.

For today, this repository contains only the project folders and route wiring. Feature implementation, models, authentication logic, dashboards, and real-time queue updates can be added in later phases.

## Tech Stack

- Python 3.11+
- Django 5
- SQLite for local development

## Current Scope

- Django project setup
- App folders created
- Route files created
- Placeholder views added so routes can be opened
- Documentation for planned pages and routes

## Folder Structure

```text
smart-queue-management-system/
├── accounts/
│   ├── urls.py
│   └── views.py
├── config/
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── dashboard/
│   ├── urls.py
│   └── views.py
├── queues/
│   ├── urls.py
│   └── views.py
├── static/
│   └── css/
├── templates/
│   ├── accounts/
│   ├── dashboard/
│   └── queues/
├── docs/
├── manage.py
├── requirements.txt
└── README.md
```

## Routes Created

| URL | Purpose |
| --- | --- |
| `/` | User dashboard route |
| `/staff/` | Staff dashboard route |
| `/manage/` | Admin dashboard route |
| `/accounts/register/` | Register route |
| `/accounts/login/` | Login route |
| `/accounts/logout/` | Logout route |
| `/queue/take-token/` | Take token route |
| `/queue/live/` | Live queue route |
| `/queue/history/` | Queue history route |
| `/queue/staff/call-next/` | Call next route |
| `/queue/staff/token/<id>/<action>/` | Token action route |
| `/admin/` | Django admin route |

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

Run the development server:

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## GitHub Repository

[https://github.com/lokaraj-shnoor/smart-queue-management-system](https://github.com/lokaraj-shnoor/smart-queue-management-system)

Push local changes:

```powershell
git push -u origin main
```

## Next Phases

- Add authentication
- Add roles: `USER`, `STAFF`, `ADMIN`
- Add queue models
- Add dashboards
- Add token generation
- Add search and filtering
- Add live updates using WebSockets or Django Channels
- Add responsive UI

## License

MIT
