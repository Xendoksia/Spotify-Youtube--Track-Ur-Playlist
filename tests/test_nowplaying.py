import unittest
from unittest import mock

from playlist_tracker.music import nowplaying
from playlist_tracker.music.nowplaying import LocalTracker, Snapshot

SONG = 210_000  # a 3:30 song


def song(title="Snuff", position=None, playing=True, duration=SONG):
    return Snapshot("Slipknot", title, "All Hope Is Gone", playing, position, duration)


class TrackerTest(unittest.TestCase):
    """Feeds the recorder what Windows would report, with a fake clock and a fake database."""

    def setUp(self):
        self.now = 1000.0
        self.records: list[dict] = []
        self.updates: dict[int, int] = {}
        patches = [
            mock.patch.object(nowplaying.time, "monotonic", lambda: self.now),
            mock.patch.object(nowplaying.listening, "record_local", self._record),
            mock.patch.object(nowplaying.listening, "update_local",
                              lambda play_id, ms: self.updates.__setitem__(play_id, ms)),
            mock.patch.object(nowplaying, "save_cover", lambda play: None),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.tracker = LocalTracker()
        self.tracker._last_tick = self.now

    def _record(self, play):
        self.records.append(dict(play))
        return len(self.records)

    def run_for(self, seconds: float, snapshot, start_position=None):
        """Report snapshot every 3 seconds for a while. Given start_position, the position moves on from it while
        playing; otherwise the snapshot's own position is reported every time."""
        position = snapshot.position_ms if start_position is None else start_position
        for _ in range(int(seconds // 3)):
            self.now += 3
            if start_position is not None and snapshot.playing:
                position += 3000
            self.tracker._tick(Snapshot(snapshot.artist, snapshot.title, snapshot.album, snapshot.playing,
                                        position, snapshot.duration_ms))

    def ms(self) -> int:
        return self.tracker._play["ms"] if self.tracker._play else 0

    def test_a_song_counts_after_30_seconds(self):
        self.tracker._tick(song(position=0))
        self.run_for(27, song(), 0)
        self.assertEqual(self.records, [])
        self.run_for(3, song(), 27_000)
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0]["name"], "Snuff")
        self.assertGreaterEqual(self.records[0]["ms"], 30_000)

    def test_a_song_skipped_early_is_not_recorded(self):
        self.tracker._tick(song(position=0))
        self.run_for(15, song(), 0)
        self.tracker._tick(song("Psychosocial", position=0))
        self.assertEqual(self.records, [])

    def test_paused_time_is_not_counted(self):
        self.tracker._tick(song(position=0))
        self.run_for(12, song(), 0)
        self.run_for(60, song(position=12_000, playing=False))
        self.assertEqual(self.ms(), 12_000)
        self.assertEqual(self.tracker.state, "paused")

    def test_the_next_song_saves_the_listening_time(self):
        self.tracker._tick(song(position=0))
        self.run_for(60, song(), 0)
        self.tracker._tick(song("Psychosocial", position=0))
        self.assertEqual(self.updates[1], 60_000)
        self.assertEqual(self.tracker._play["name"], "Psychosocial")

    def test_starting_the_song_again_is_a_new_play(self):
        self.tracker._tick(song(position=0))
        self.run_for(60, song(), 0)
        self.now += 3
        self.tracker._tick(song(position=1000))
        self.run_for(30, song(), 1000)
        self.assertEqual(len(self.records), 2)

    def test_briefly_unreadable_continues_the_same_play(self):
        self.tracker._tick(song(position=0))
        self.run_for(60, song(), 0)
        self.now += 3
        self.tracker._tick(None)
        self.now += 6
        self.tracker._tick(song(position=69_000))
        self.run_for(30, song(), 69_000)
        self.assertEqual(len(self.records), 1, "the play went on, it was not recorded twice")
        self.assertEqual(self.ms(), 90_000)

    def test_on_repeat_without_a_position_reset_the_play_is_closed_at_the_songs_length(self):
        self.tracker._tick(song(position=0))
        # Windows keeps reporting the end of the song while it plays again
        self.run_for(SONG / 1000 + 30, song(position=SONG))
        self.assertEqual(self.updates[1], SONG)
        self.assertEqual(len(self.records), 2)
        self.assertLess(self.ms(), 40_000)

    def test_a_sleeping_computer_does_not_count_as_listening(self):
        self.tracker._tick(song(position=0))
        self.run_for(30, song(), 0)
        self.now += 3600
        self.tracker._tick(song(position=33_000))
        self.assertLessEqual(self.ms(), 30_000 + nowplaying.MAX_TICK_MS)

    def test_spotify_closing_finishes_the_play(self):
        self.tracker._tick(song(position=0))
        self.run_for(45, song(), 0)
        self.now += 3
        self.tracker._tick(None)
        self.assertIsNone(self.tracker._play)
        self.assertEqual(self.updates[1], 45_000)
        self.assertEqual(self.tracker.state, "idle")

    def test_ads_keep_the_play(self):
        self.tracker._tick(song(position=0))
        self.run_for(30, song(), 0)
        self.run_for(30, Snapshot("", "", "", True))
        self.assertIsNotNone(self.tracker._play)
        self.assertEqual(self.ms(), 30_000)


if __name__ == "__main__":
    unittest.main()
