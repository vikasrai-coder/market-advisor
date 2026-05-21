alter table stocks add column if not exists cap_segment text;
alter table stocks add column if not exists exchange text;
alter table stocks add column if not exists currency text default 'INR';
alter table recommendations add column if not exists cap_segment text;
