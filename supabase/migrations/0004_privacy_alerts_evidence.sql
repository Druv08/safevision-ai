-- SafeVision AI - review workflow, evidence integrity, privacy retention and alerts.
-- Apply after 0003 (see supabase/README.md).

-- ---------------------------------------------------------------------------
-- violations
-- ---------------------------------------------------------------------------
alter table public.violations drop constraint violations_status_check;
alter table public.violations
  add constraint violations_status_check
    check (status in ('new', 'acknowledged', 'action_taken', 'closed')),
  add column action_taken_by uuid references auth.users (id) on delete set null,
  -- Recorded by the reviewer. 'ppe_not_issued' is the site's failure, not the worker's.
  add column cause text
    check (cause in ('ppe_not_issued', 'ppe_not_worn', 'ppe_damaged', 'false_detection', 'other')),
  -- SHA-256 of the stored (blurred) screenshot, taken at capture.
  add column screenshot_sha256 text check (screenshot_sha256 ~ '^[0-9a-f]{64}$'),
  -- Unblurred original: Fernet-encrypted object in the same private bucket, kept
  -- until original_expires_at (ORIGINAL_RETENTION_HOURS) unless on legal hold.
  add column original_path text,
  add column original_sha256 text check (original_sha256 ~ '^[0-9a-f]{64}$'),
  add column original_expires_at timestamptz,
  -- Set when retention deleted the screenshot; the row and its hash stay for statistics.
  add column screenshot_deleted_at timestamptz,
  add column legal_hold boolean not null default false,
  add column legal_hold_reason text;

-- What the retention job scans for.
create index violations_retention_idx on public.violations (created_at)
  where screenshot_path is not null and not legal_hold;
create index violations_original_expiry_idx on public.violations (original_expires_at)
  where original_path is not null and not legal_hold;
create index violations_zone_idx on public.violations (zone_id);

-- The bucket also holds the encrypted originals (opaque bytes, not JPEG).
update storage.buckets
  set allowed_mime_types = array['image/jpeg', 'application/octet-stream']
  where id = 'violation-screenshots';

-- ---------------------------------------------------------------------------
-- alert recipients and the delivery log
-- ---------------------------------------------------------------------------
create table public.alert_recipients (
  id         uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  name       text not null check (length(name) between 1 and 100),
  channel    text not null check (channel in ('whatsapp', 'webhook')),
  -- +E.164 phone number, or a webhook URL (validated by the backend)
  address    text not null check (length(address) between 1 and 500),
  language   text not null default 'en' check (language in ('en', 'hi')),
  enabled    boolean not null default true
);

-- One row per (episode, recipient). The unique constraint IS the de-duplication:
-- the backend inserts this row before sending, so a second attempt fails here.
create table public.alerts (
  id             uuid primary key default gen_random_uuid(),
  created_at     timestamptz not null default now(),
  violation_id   uuid not null references public.violations (id) on delete cascade,
  recipient_id   uuid references public.alert_recipients (id) on delete set null,
  recipient_name text,
  channel        text not null,
  status         text not null check (status in ('sending', 'sent', 'logged', 'failed')),
  error          text,
  sent_at        timestamptz,
  unique (violation_id, recipient_id)
);

create index alerts_created_at_idx on public.alerts (created_at desc);

-- Phone numbers are personal data: no browser access at all, API (admin) only.
alter table public.alert_recipients enable row level security;
alter table public.alerts           enable row level security;

-- ---------------------------------------------------------------------------
-- audit_log: append-only for every role, the service role included
-- ---------------------------------------------------------------------------
-- 0001 let service_role update and delete. Now nobody can; truncate is blocked
-- too. Only the table owner could still disable the triggers (that is itself a
-- DDL change, visible in Postgres logs).
create or replace function public.audit_log_block_changes()
returns trigger
language plpgsql
as $$
begin
  raise exception 'audit_log is append-only (% refused)', lower(tg_op);
end;
$$;

create trigger audit_log_no_truncate
  before truncate on public.audit_log
  for each statement execute function public.audit_log_block_changes();

revoke update, delete, truncate on public.audit_log from service_role;
