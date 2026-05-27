-- Strategy builder foundation: user-owned strategies and immutable versions.

create table if not exists strategies (
  id uuid primary key default gen_random_uuid(),
  owner_user_id text not null,
  name text not null,
  description text,
  visibility text not null default 'private' check (visibility in ('private', 'unlisted', 'public')),
  status text not null default 'draft' check (status in ('draft', 'active', 'archived')),
  current_version_id uuid,
  created_at timestamptz not null default timezone('utc'::text, now()),
  updated_at timestamptz not null default timezone('utc'::text, now())
);

create table if not exists strategy_versions (
  id uuid primary key default gen_random_uuid(),
  strategy_id uuid not null references strategies(id) on delete cascade,
  version_number integer not null check (version_number > 0),
  version_label text not null,
  definition jsonb not null,
  checksum text not null,
  validation_status text not null default 'valid' check (validation_status in ('valid', 'invalid')),
  validation_errors jsonb not null default '[]'::jsonb,
  validation_warnings jsonb not null default '[]'::jsonb,
  notes text,
  created_by_user_id text not null,
  created_at timestamptz not null default timezone('utc'::text, now()),
  unique (strategy_id, version_number)
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'strategies_current_version_fk'
  ) then
    alter table strategies
      add constraint strategies_current_version_fk
      foreign key (current_version_id) references strategy_versions(id) on delete set null;
  end if;
end $$;

create index if not exists idx_strategies_owner_updated on strategies(owner_user_id, updated_at desc);
create index if not exists idx_strategy_versions_strategy on strategy_versions(strategy_id, version_number desc);
create index if not exists idx_strategy_versions_definition_gin on strategy_versions using gin(definition);

alter table strategies enable row level security;
alter table strategy_versions enable row level security;

drop policy if exists "owners read strategies" on strategies;
drop policy if exists "owners write strategies" on strategies;
drop policy if exists "owners read strategy versions" on strategy_versions;
drop policy if exists "owners write strategy versions" on strategy_versions;

create policy "owners read strategies"
  on strategies for select
  using (owner_user_id = auth.uid()::text or visibility = 'public');

create policy "owners write strategies"
  on strategies for all
  using (owner_user_id = auth.uid()::text)
  with check (owner_user_id = auth.uid()::text);

create policy "owners read strategy versions"
  on strategy_versions for select
  using (
    exists (
      select 1
      from strategies s
      where s.id = strategy_versions.strategy_id
        and (s.owner_user_id = auth.uid()::text or s.visibility = 'public')
    )
  );

create policy "owners write strategy versions"
  on strategy_versions for all
  using (
    exists (
      select 1
      from strategies s
      where s.id = strategy_versions.strategy_id
        and s.owner_user_id = auth.uid()::text
    )
  )
  with check (
    exists (
      select 1
      from strategies s
      where s.id = strategy_versions.strategy_id
        and s.owner_user_id = auth.uid()::text
    )
  );
