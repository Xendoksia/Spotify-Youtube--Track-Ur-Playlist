-- Playlist check history and the settings that follow the user (language, theme), synced like the plays.

-- Changes found by checking playlists, as the events table of history.db / youtube_history.db. uid identifies an
-- event on every device; device_id is the device whose check found it. Rows are only added, never changed.
create table if not exists public.playlist_events (
    user_id uuid not null default auth.uid() references auth.users on delete cascade,
    uid text not null,
    device_id text not null,
    service text not null,
    playlist_id text not null,
    checked_at text not null,
    event text not null,
    uri text,
    name text,
    artist text,
    album text,
    added_at text,
    updated_at timestamptz not null default now(),
    primary key (user_id, uid)
);
create index if not exists playlist_events_updated on public.playlist_events (user_id, updated_at);

drop trigger if exists playlist_events_touch on public.playlist_events;
create trigger playlist_events_touch before insert or update on public.playlist_events
    for each row execute function public.touch_updated_at();

alter table public.playlist_events enable row level security;
drop policy if exists "own events" on public.playlist_events;
create policy "own events" on public.playlist_events for all to authenticated
    using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
grant select, insert, update on public.playlist_events to authenticated;

-- One row per user: the settings as JSON ({"LANGUAGE": "tr", "THEME": "dark"}); the latest change wins
create table if not exists public.settings (
    user_id uuid primary key default auth.uid() references auth.users on delete cascade,
    data jsonb not null,
    changed_at text not null,
    updated_at timestamptz not null default now()
);

drop trigger if exists settings_latest on public.settings;
create trigger settings_latest before insert or update on public.settings
    for each row execute function public.keep_latest_change();

alter table public.settings enable row level security;
drop policy if exists "own settings" on public.settings;
create policy "own settings" on public.settings for all to authenticated
    using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
grant select, insert, update on public.settings to authenticated;
