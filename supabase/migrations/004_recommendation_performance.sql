-- Migration 004: Add performance tracking to recommendations
alter table recommendations add column if not exists target_price numeric;
alter table recommendations add column if not exists stop_loss numeric;
alter table recommendations add column if not exists performance_status text default 'pending' check (performance_status in ('pending', 'target_hit', 'stopped_out'));
alter table recommendations add column if not exists exit_price numeric;
