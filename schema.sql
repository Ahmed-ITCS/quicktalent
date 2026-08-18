-- QuickTalent — Supabase schema
-- Run these in the Supabase SQL editor.
-- The "candidates" table already exists with your loaded data.
-- This creates: hr_accounts, contacts, and adds a "status" column to candidates if missing.

create table if not exists public.hr_accounts (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  password_hash text not null,
  company_name text not null,
  phone text,
  role text not null default 'hr' check (role in ('hr', 'admin')),
  is_verified boolean not null default false,
  is_blocked boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.contacts (
  id uuid primary key default gen_random_uuid(),
  hr_id uuid not null references public.hr_accounts(id) on delete cascade,
  candidate_id uuid not null references public.candidates(id) on delete cascade,
  status text not null default 'requested',
  created_at timestamptz not null default now(),
  unique (hr_id, candidate_id)
);

-- Rollout note: pre-feature contact requests were already visible to HR.
-- Run once after deploying to unlock them:
-- update public.contacts set status = 'approved' where status = 'requested';

-- Optional: track employment status on candidates ('available' | 'employed' | 'closed')
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'candidates' and column_name = 'status'
  ) then
    alter table public.candidates add column status text not null default 'available';
  end if;
end $$;

-- If RLS is enabled, add policies (or disable RLS on these tables for app-key access):
alter table public.hr_accounts enable row level security;
alter table public.contacts enable row level security;
create policy "hr_accounts app access" on public.hr_accounts for all using (true) with check (true);
create policy "contacts app access" on public.contacts for all using (true) with check (true);
