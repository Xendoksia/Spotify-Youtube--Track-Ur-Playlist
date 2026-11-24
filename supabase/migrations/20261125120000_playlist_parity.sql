-- The phone shows and does what the desktop app's playlist tracking page does: the playlists found in an account
-- and not decided on yet, the last check and the next automatic one, and a check asked for from the phone.

-- seen: false for a playlist found in the account that nobody decided to track or not; size as the account gave
-- it; found_at when it was found. A found playlist is sent with the oldest changed_at, so it never undoes tracking
-- decided on another device (keep_latest_change).
alter table public.tracked_playlists add column if not exists seen boolean not null default true;
alter table public.tracked_playlists add column if not exists size integer;
alter table public.tracked_playlists add column if not exists found_at text;

-- One row per user. The desktop app writes its last check of the tracked playlists (checked_at, checked_count)
-- and its next automatic check; the phone writes check_requested_at, which the desktop app answers with a check.
create table if not exists public.playlist_status (
    user_id uuid primary key default auth.uid() references auth.users on delete cascade,
    checked_at text,
    checked_count integer,
    next_check text,
    check_requested_at text,
    updated_at timestamptz not null default now()
);

drop trigger if exists playlist_status_touch on public.playlist_status;
create trigger playlist_status_touch before insert or update on public.playlist_status
    for each row execute function public.touch_updated_at();

alter table public.playlist_status enable row level security;
drop policy if exists "own status" on public.playlist_status;
create policy "own status" on public.playlist_status for all to authenticated
    using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
grant select, insert, update on public.playlist_status to authenticated;
