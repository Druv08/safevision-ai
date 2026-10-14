-- SafeVision AI - violation episodes and compliance observations.
-- Apply after 0001_init.sql (see supabase/README.md).

-- One violation row is now one episode: one tracked person missing one item
-- for at least VIOLATION_WINDOW_SECONDS. Times are seconds from the start of
-- the source video (0 for a single image). track_id is null for single images.
alter table public.violations
  add column track_id        integer,
  add column episode_start_s real check (episode_start_s >= 0),
  add column episode_end_s   real check (episode_end_s >= episode_start_s);

-- One row per tracked person per item per processed image or video, whether or
-- not they violated, so a compliance rate can be computed:
--   rate = compliant / (compliant + violation); 'unknown' (item never seen) is excluded.
create table public.observations (
  id             bigint generated always as identity primary key,
  created_at     timestamptz not null default now(),
  source         text not null check (source in ('image', 'video', 'camera')),
  track_id       integer,
  item           text not null check (item in ('helmet', 'vest')),
  outcome        text not null check (outcome in ('compliant', 'violation', 'unknown')),
  frames_worn    integer not null default 0,
  frames_missing integer not null default 0,
  frames_unknown integer not null default 0,
  first_s        real,
  last_s         real,
  model_version  text
);

create index observations_created_at_idx on public.observations (created_at desc);
create index observations_item_outcome_idx on public.observations (item, outcome);

alter table public.observations enable row level security;

-- Same as violations: any logged-in user can read; writes come from the backend only.
create policy "observations: authenticated read"
  on public.observations for select
  to authenticated
  using (true);
