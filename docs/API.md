# Route Plan

This file lists the Django routes currently created in the scaffold.

## Authentication Routes

| URL | View | Purpose |
| --- | --- | --- |
| `/accounts/register/` | `accounts.views.register` | Register route placeholder |
| `/accounts/login/` | `accounts.views.login_view` | Login route placeholder |
| `/accounts/logout/` | `accounts.views.logout_view` | Logout route placeholder |

## Dashboard Routes

| URL | View | Purpose |
| --- | --- | --- |
| `/` | `dashboard.views.dashboard` | User dashboard route placeholder |
| `/staff/` | `dashboard.views.staff_dashboard` | Staff dashboard route placeholder |
| `/manage/` | `dashboard.views.admin_dashboard` | Admin dashboard route placeholder |

## Queue Routes

| URL | View | Purpose |
| --- | --- | --- |
| `/queue/take-token/` | `queues.views.take_token` | Token generation route placeholder |
| `/queue/live/` | `queues.views.live_queue` | Live queue route placeholder |
| `/queue/history/` | `queues.views.queue_history` | Queue history route placeholder |
| `/queue/staff/call-next/` | `queues.views.call_next` | Staff call-next route placeholder |
| `/queue/staff/token/<id>/<action>/` | `queues.views.change_token_status` | Token action route placeholder |

## Admin Route

| URL | Purpose |
| --- | --- |
| `/admin/` | Django admin |
