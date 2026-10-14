-- SafeVision AI - initial schema.
-- Apply with `supabase db push` or paste into the Supabase SQL editor (see supabase/README.md).
--
-- The FastAPI backend talks to Postgres and Storage with the service-role key,
-- which bypasses RLS. The policies below therefore only govern what the
-- browser (anon key + user JWT) can do directly.

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
create table public.profiles (
  id         uuid primary key references auth.users (id) on delete cascade,
  full_name  text,
  role       text not null default 'viewer' check (role in ('admin', 'viewer')),
  created_at timestamptz not null default now()
);

-- Every new auth user gets a viewer profile. Promote to admin by hand (README).
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name, role)
  values (new.id, new.raw_user_meta_data ->> 'full_name', 'viewer');
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- security definer so policies can check the caller's role without recursing
-- into the profiles RLS policy.
create function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.profiles where id = auth.uid() and role = 'admin'
  );
$$;

-- ---------------------------------------------------------------------------
-- violations
-- ---------------------------------------------------------------------------
create table public.violations (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),
  type            text not null check (type in ('no_helmet', 'no_vest')),
  confidence      real not null check (confidence >= 0 and confidence <= 1),
  source          text not null check (source in ('image', 'video', 'camera')),
  -- Object key inside the private screenshots bucket, never a URL or server path.
  screenshot_path text,
  model_version   text,
  status          text not null default 'new' check (status in ('new', 'acknowledged', 'closed')),
  acknowledged_by uuid references auth.users (id) on delete set null,
  closed_by       uuid references auth.users (id) on delete set null,
  note            text
);

create index violations_created_at_idx on public.violations (created_at desc);
create index violations_type_idx on public.violations (type);

-- ---------------------------------------------------------------------------
-- audit_log (append-only)
-- ---------------------------------------------------------------------------
-- user_id deliberately has no foreign key: an FK action (set null / cascade)
-- would be an update or delete, and audit rows must never change.
create table public.audit_log (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  user_id    uuid,
  action     text not null,
  target_id  uuid,
  detail     jsonb
);

create index audit_log_created_at_idx on public.audit_log (created_at desc);

create function public.audit_log_block_changes()
returns trigger
language plpgsql
as $$
begin
  if current_user <> 'service_role' then
    raise exception 'audit_log is append-only (only service_role may % rows)', lower(tg_op);
  end if;
  return coalesce(new, old);
end;
$$;

create trigger audit_log_no_update_delete
  before update or delete on public.audit_log
  for each row execute function public.audit_log_block_changes();

revoke update, delete, truncate on public.audit_log from anon, authenticated;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.profiles   enable row level security;
alter table public.violations enable row level security;
alter table public.audit_log  enable row level security;

-- profiles: a user can read only their own row. No client writes.
create policy "profiles: read own"
  on public.profiles for select
  to authenticated
  using (id = auth.uid());

-- violations: any logged-in user can read; only admins can update/delete.
-- Inserts come from the backend (service role) only.
create policy "violations: authenticated read"
  on public.violations for select
  to authenticated
  using (true);

create policy "violations: admin update"
  on public.violations for update
  to authenticated
  using (public.is_admin())
  with check (public.is_admin());

create policy "violations: admin delete"
  on public.violations for delete
  to authenticated
  using (public.is_admin());

-- audit_log: only admins can read. Writes come from the backend only.
create policy "audit_log: admin read"
  on public.audit_log for select
  to authenticated
  using (public.is_admin());

-- ---------------------------------------------------------------------------
-- Storage: private bucket for violation screenshots
-- ---------------------------------------------------------------------------
-- No policies are created on storage.objects for this bucket, so only the
-- service role can read or write. Users see screenshots through short-lived
-- signed URLs issued by the backend.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('violation-screenshots', 'violation-screenshots', false, 5242880, array['image/jpeg'])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;
