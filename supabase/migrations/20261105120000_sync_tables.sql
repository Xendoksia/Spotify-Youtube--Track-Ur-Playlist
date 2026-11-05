-- Tables the app syncs to (plays, tracked playlists). Applied with `npx supabase db push --remote=<project ref>`;
-- every statement can run again harmlessly.
-- Every row belongs to the logged-in user (user_id), and row level security lets a user reach only their own.

-- Plays, as listening.db's listens table. uid identifies a play on every device; device_id is the device that
-- recorded it. played_at stays text ("2026-11-05T10:18:16Z") so it comes back exactly as it was sent.
create table if not exists public.plays (
    user_id uuid not null default auth.uid() references auth.users on delete cascade,
    uid text not null,
    device_id text not null,
    device_name text,
    played_at text not null,
    source text not null,
    artist text,
    name text,
    album text,
    ms_played integer,
    updated_at timestamptz not null default now(),
    primary key (user_id, uid)
);
-- Devices pull what changed since their last pull
create index if not exists plays_updated on public.plays (user_id, updated_at);

create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end $$;

drop trigger if exists plays_touch on public.plays;
create trigger plays_touch before insert or update on public.plays
    for each row execute function public.touch_updated_at();

alter table public.plays enable row level security;
drop policy if exists "own plays" on public.plays;
create policy "own plays" on public.plays for all to authenticated
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
grant select, insert, update on public.plays to authenticated;

-- Tracked playlists, as the playlists table of history.db / youtube_history.db. changed_at is when the user
-- tracked or untracked it on a device: the latest change wins, an older one arriving later is ignored.
create table if not exists public.tracked_playlists (
    user_id uuid not null default auth.uid() references auth.users on delete cascade,
    service text not null,
    playlist_id text not null,
    name text,
    tracked boolean not null,
    changed_at text not null,
    updated_at timestamptz not null default now(),
    primary key (user_id, service, playlist_id)
);
create index if not exists tracked_playlists_updated on public.tracked_playlists (user_id, updated_at);

create or replace function public.keep_latest_change() returns trigger language plpgsql as $$
begin
    if tg_op = 'UPDATE' and new.changed_at < old.changed_at then
        return old;
    end if;
    new.updated_at := now();
    return new;
end $$;

drop trigger if exists tracked_playlists_latest on public.tracked_playlists;
create trigger tracked_playlists_latest before insert or update on public.tracked_playlists
    for each row execute function public.keep_latest_change();

alter table public.tracked_playlists enable row level security;
drop policy if exists "own playlists" on public.tracked_playlists;
create policy "own playlists" on public.tracked_playlists for all to authenticated
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
grant select, insert, update on public.tracked_playlists to authenticated;
