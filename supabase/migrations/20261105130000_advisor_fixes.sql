-- Fixes for Supabase's database advisors.

-- Functions run with a fixed search_path, so a table of the same name elsewhere cannot stand in for one of ours
alter function public.touch_updated_at() set search_path = '';
alter function public.keep_latest_change() set search_path = '';

-- auth.uid() inside a select is evaluated once per query instead of once per row
drop policy if exists "own plays" on public.plays;
create policy "own plays" on public.plays for all to authenticated
    using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "own playlists" on public.tracked_playlists;
create policy "own playlists" on public.tracked_playlists for all to authenticated
    using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
