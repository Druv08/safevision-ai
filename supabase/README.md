# Supabase setup

SafeVision uses one Supabase project for Postgres (violations, profiles,
audit log), Storage (screenshots) and Auth (login).

`migrations/0001_init.sql` creates:

| Object | Purpose | Who can access it from the browser |
|---|---|---|
| `profiles` | One row per user: `full_name`, `role` (`admin` or `viewer`). Created automatically by a trigger when a user signs up, always as `viewer`. | A user can read only their own row. Nobody can write. |
| `violations` | One row per logged violation. `screenshot_path` is an object key in the screenshots bucket, never a URL or a server path. | Any logged-in user can read. Only admins can update or delete. |
| `audit_log` | Append-only record of evidence views, exports, deletes and status changes. | Only admins can read. Nobody but the service role can update or delete (RLS + a trigger). |
| Storage bucket `violation-screenshots` | Private bucket, JPEG only, 5 MB per file. | No policies, so no direct access. Screenshots are shown through signed URLs that the backend creates and that expire after `SIGNED_URL_TTL_SECONDS` (default 5 minutes). |

Row Level Security is enabled on all three tables. The backend uses the
service-role key, which bypasses RLS, so the API routes do their own role
checks (`backend/auth.py`).

## 1. Apply the migration

Either:

- **Dashboard:** open SQL Editor, paste the contents of
  `migrations/0001_init.sql`, and run it once.
- **CLI:** from the repository root,
  ```bash
  supabase link --project-ref <your-project-ref>
  supabase db push
  ```

Running it a second time fails (the tables already exist); that is expected.

## 2. Turn off public sign-ups

Every new auth user becomes a `viewer` who can read all violations. Unless you
want anyone with the site URL to be able to register, go to
**Authentication → Sign In / Providers** and disable "Allow new users to sign
up". Then create accounts yourself under **Authentication → Users → Add user**
(or invite them by email). The app has no sign-up page.

## 3. Make the first user an admin

1. Create the user (Authentication → Users → Add user, tick "Auto Confirm User").
2. In SQL Editor run, with that user's email:

   ```sql
   update public.profiles
   set role = 'admin'
   where id = (select id from auth.users where email = 'you@example.com');
   ```

3. Check it:

   ```sql
   select u.email, p.role from public.profiles p join auth.users u on u.id = p.id;
   ```

The user must sign out and in again for the frontend to pick up the new role.
Use the same `update` with `'viewer'` to demote someone.

## 4. Keys

From **Project Settings → API**:

| Key | Goes in | Notes |
|---|---|---|
| Project URL | `backend/.env` `SUPABASE_URL` and `frontend/.env` `VITE_SUPABASE_URL` | |
| `anon` / publishable key | `frontend/.env` `VITE_SUPABASE_ANON_KEY` | Safe in the browser; RLS limits what it can do. |
| `service_role` / secret key | `backend/.env` `SUPABASE_SERVICE_ROLE_KEY` **only** | Bypasses RLS. Never put it in the frontend or in any `VITE_` variable, and never commit it. |

## 5. Import old CSV data (optional)

If you have a `violations_log.csv` from the earlier CSV-based versions:

```bash
cd backend
python -m scripts.migrate_csv ../ai-model/outputs/violations/violations_log.csv --dry-run
python -m scripts.migrate_csv ../ai-model/outputs/violations/violations_log.csv
```

It reads both the 8-column backend format and the 9-column CLI format,
uploads each screenshot under a new server-generated key, and can be re-run
safely (already-imported rows are skipped). Use `--screenshots-dir` if the
screenshots have moved since the CSV was written.
