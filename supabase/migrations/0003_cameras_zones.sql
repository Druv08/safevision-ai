-- SafeVision AI - network cameras (RTSP) and per-camera zones.
-- Apply after 0002 (see supabase/README.md).

-- ---------------------------------------------------------------------------
-- cameras
-- ---------------------------------------------------------------------------
-- `url` never contains credentials. Username and password are stored only in
-- `credentials_enc`, encrypted by the backend (Fernet, CAMERA_SECRET_KEY), and
-- are never returned by the API.
create table public.cameras (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  name            text not null check (length(name) between 1 and 100),
  url             text not null,
  credentials_enc text,
  sample_fps      real not null default 5 check (sample_fps > 0 and sample_fps <= 30),
  default_policy  text not null default 'both' check (default_policy in ('both', 'helmet', 'vest', 'none')),
  enabled         boolean not null default false
);

-- ---------------------------------------------------------------------------
-- zones: polygon in normalised image coordinates, [[x, y], ...] with 0 <= x, y <= 1
-- ---------------------------------------------------------------------------
create table public.zones (
  id         uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  camera_id  uuid not null references public.cameras (id) on delete cascade,
  name       text not null check (length(name) between 1 and 100),
  policy     text not null check (policy in ('both', 'helmet', 'vest', 'none', 'no_entry')),
  polygon    jsonb not null check (jsonb_typeof(polygon) = 'array' and jsonb_array_length(polygon) between 3 and 64)
);

create index zones_camera_idx on public.zones (camera_id);

-- ---------------------------------------------------------------------------
-- violations / observations: link to camera and zone, zone intrusions, wall-clock episode times
-- ---------------------------------------------------------------------------
alter table public.violations drop constraint violations_type_check;
alter table public.violations
  add constraint violations_type_check check (type in ('no_helmet', 'no_vest', 'zone_intrusion')),
  add column camera_id  uuid references public.cameras (id) on delete set null,
  add column zone_id    uuid references public.zones (id) on delete set null,
  -- For camera streams episode_start_s / episode_end_s are seconds since the
  -- stream worker started; these give the actual times.
  add column started_at timestamptz,
  add column ended_at   timestamptz;

create index violations_camera_idx on public.violations (camera_id);

alter table public.observations
  add column camera_id uuid references public.cameras (id) on delete set null;

-- ---------------------------------------------------------------------------
-- RLS: no policies, so browsers (anon / authenticated) cannot read or write
-- these tables at all; everything goes through the backend API, which never
-- returns credentials_enc.
-- ---------------------------------------------------------------------------
alter table public.cameras enable row level security;
alter table public.zones   enable row level security;
