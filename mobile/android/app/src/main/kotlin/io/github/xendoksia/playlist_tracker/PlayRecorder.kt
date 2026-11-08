package io.github.xendoksia.playlist_tracker

import android.content.ComponentName
import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

/**
 * Records what Spotify plays on the phone, by the desktop app's rules (music/nowplaying.py): a song counts as
 * played once it has been listened to for 30 seconds, and the time actually listened is stored. Runs in
 * MediaListener, so it goes on while the app is closed; the app sends the plays to Supabase (PlayStore).
 *
 * The time listened is how far the song moved on while playing, so the hours Android keeps the app asleep are
 * counted once it wakes, and seeking forward counts only as the time that passed.
 */
class PlayRecorder(context: Context, private val listener: ComponentName) {
    companion object {
        const val MIN_PLAY_MS = 30_000L
        // A tick while playing, so a play is stored at 30 seconds and its time saved now and then
        const val TICK_MS = 5_000L
        const val SAVE_EVERY_MS = 30_000L
        // Without a position the time between two ticks counts, at most this much (the phone slept)
        const val MAX_TICK_MS = 15_000L
        // A song seen again this soon after its play ended, past its start, is the same play going on
        const val RESUME_MS = 60_000L
        // Before this position a song seen again, or jumping back, counts as started over
        const val RESTART_POSITION_MS = 15_000L

        /** The key of the play stored last while it still plays, for the mini player's "recorded" mark */
        @Volatile
        var recordedKey: String? = null

        /** Told when a play is stored (NowPlaying sends the mini player the change) */
        @Volatile
        var onRecorded: (() -> Unit)? = null

        fun textKey(text: String) = text.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")

        fun key(artist: String, title: String) = textKey(artist) + "|" + textKey(title)

        fun utc(millis: Long): String =
            SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
                .format(Date(millis))
    }

    private class Play(
        val key: String, val artist: String, val name: String, var album: String, val playedAt: String,
        var ms: Long = 0, var savedMs: Long = 0, var uid: String? = null, var position: Long? = null,
    )

    private val store = PlayStore(context)
    private val sessions = context.getSystemService(MediaSessionManager::class.java)
    private val main = Handler(Looper.getMainLooper())
    private var controller: MediaController? = null
    private var play: Play? = null
    private var ended: Pair<Play, Long>? = null
    private var lastTick = SystemClock.elapsedRealtime()

    private val sessionsChanged = MediaSessionManager.OnActiveSessionsChangedListener { follow(it) }
    private val callback = object : MediaController.Callback() {
        override fun onMetadataChanged(metadata: MediaMetadata?) = tick()
        override fun onPlaybackStateChanged(state: PlaybackState?) = tick()
        override fun onSessionDestroyed() = follow(null)
    }
    private val ticker = Runnable { tick() }

    fun start() {
        try {
            sessions.addOnActiveSessionsChangedListener(sessionsChanged, listener, main)
            follow(sessions.getActiveSessions(listener))
        } catch (_: SecurityException) {
            // No notification access (taken back): nothing can be read
        }
    }

    fun stop() {
        tick()
        finish()
        sessions.removeOnActiveSessionsChangedListener(sessionsChanged)
        controller?.unregisterCallback(callback)
        controller = null
        main.removeCallbacks(ticker)
    }

    private fun follow(active: List<MediaController>?) {
        val spotify = active?.firstOrNull { it.packageName == NowPlaying.SPOTIFY }
        if (spotify?.sessionToken != controller?.sessionToken) {
            controller?.unregisterCallback(callback)
            controller = spotify
            spotify?.registerCallback(callback, main)
        }
        tick()
    }

    private fun tick() {
        main.removeCallbacks(ticker)
        val now = SystemClock.elapsedRealtime()
        val elapsed = now - lastTick
        lastTick = now
        val spotify = controller
        val metadata = spotify?.metadata
        val state = spotify?.playbackState
        val title = metadata?.getString(MediaMetadata.METADATA_KEY_TITLE)
        val artist = metadata?.getString(MediaMetadata.METADATA_KEY_ARTIST)
        // Spotify Connect: the phone controls a song playing on another device, which records it itself
        val remote = spotify?.playbackInfo?.playbackType == MediaController.PlaybackInfo.PLAYBACK_TYPE_REMOTE
        if (spotify == null || title.isNullOrBlank() || artist.isNullOrBlank() || remote) {
            if (spotify == null || remote) finish()
            return
        }
        val playing = state?.state == PlaybackState.STATE_PLAYING
        val position = state?.takeIf { it.state != PlaybackState.STATE_NONE && it.position >= 0 }?.let {
            if (playing) it.position + ((now - it.lastPositionUpdateTime) * it.playbackSpeed).toLong() else it.position
        }
        val key = key(artist, title)
        var current = play
        val previous = current?.position
        val restarted = current != null && current.key == key && current.ms >= MIN_PLAY_MS && position != null &&
            previous != null && position + 5_000 < previous && position < RESTART_POSITION_MS
        if (current != null && (current.key != key || restarted)) {
            finish()
            if (restarted) ended = null
            current = null
        }
        val album = metadata.getString(MediaMetadata.METADATA_KEY_ALBUM) ?: ""
        if (current == null) {
            val started = System.currentTimeMillis() - (position?.takeIf { it < 15 * 60_000 } ?: 0)
            current = resumed(key, position, now) ?: stored(artist, title, started) ?: Play(
                key, artist, title, album, utc(started),
            )
            play = current
        } else if (position != null && previous != null) {
            // Also when it has just paused: the song moved on until then
            current.ms += (position - previous).coerceIn(0, elapsed + 1_000)
        } else if (playing) {
            current.ms += elapsed.coerceAtMost(MAX_TICK_MS)
        }
        current.position = position
        if (current.album.isEmpty()) current.album = album

        if (current.ms >= MIN_PLAY_MS && current.uid == null) {
            current.uid = UUID.randomUUID().toString()
            store.add(current.uid!!, current.playedAt, current.artist, current.name, current.album, current.ms)
            current.savedMs = current.ms
            recordedKey = current.key
            onRecorded?.invoke()
        } else if (current.uid != null && current.ms - current.savedMs >= SAVE_EVERY_MS) {
            save(current)
        }
        if (playing) main.postDelayed(ticker, TICK_MS)
    }

    /** The play that just ended, if this is the same song still going rather than a new play of it */
    private fun resumed(key: String, position: Long?, now: Long): Play? {
        val last = ended
        ended = null
        if (last != null && last.first.key == key && now - last.second < RESUME_MS &&
            (position == null || position >= RESTART_POSITION_MS)) {
            return last.first
        }
        return null
    }

    /**
     * The play of this song stored by the app before Android stopped it (or before an update), when the song is
     * still going: started at the same moment, by its position. Without it the rest would be a second play.
     */
    private fun stored(artist: String, title: String, started: Long): Play? {
        val (uid, playedAt, ms) = store.find(artist, title, utc(started - 15_000), utc(started + 15_000)) ?: return null
        // The album is filled in from the song's details right after
        return Play(key(artist, title), artist, title, "", playedAt, ms = ms, savedMs = ms, uid = uid).also {
            recordedKey = it.key
        }
    }

    private fun save(current: Play) {
        current.uid?.let { store.update(it, current.ms) }
        current.savedMs = current.ms
    }

    private fun finish() {
        val current = play ?: return
        save(current)
        ended = current to SystemClock.elapsedRealtime()
        play = null
        if (recordedKey == current.key) recordedKey = null
    }
}

/** The plays recorded on the phone, kept until the app has sent them to Supabase (and after, marked sent) */
class PlayStore(context: Context) :
    SQLiteOpenHelper(context.applicationContext, "phone_plays.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE plays (uid TEXT PRIMARY KEY, played_at TEXT NOT NULL, artist TEXT, name TEXT, " +
                "album TEXT, ms_played INTEGER NOT NULL, synced INTEGER NOT NULL DEFAULT 0)"
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}

    fun add(uid: String, playedAt: String, artist: String, name: String, album: String, ms: Long) {
        writableDatabase.insert("plays", null, ContentValues().apply {
            put("uid", uid)
            put("played_at", playedAt)
            put("artist", artist)
            put("name", name)
            put("album", album)
            put("ms_played", ms)
        })
    }

    /** A play of the song started between from and to (UTC texts, compared as text): its uid, start and time */
    fun find(artist: String, name: String, from: String, to: String): Triple<String, String, Long>? =
        readableDatabase.rawQuery(
            "SELECT uid, played_at, ms_played FROM plays WHERE artist = ? AND name = ? AND played_at BETWEEN ? AND ? " +
                "ORDER BY played_at DESC LIMIT 1", arrayOf(artist, name, from, to)
        ).use { if (it.moveToFirst()) Triple(it.getString(0), it.getString(1), it.getLong(2)) else null }

    /** A longer listening time is sent again */
    fun update(uid: String, ms: Long) {
        writableDatabase.execSQL("UPDATE plays SET ms_played = ?, synced = 0 WHERE uid = ?", arrayOf<Any>(ms, uid))
    }

    fun unsynced(): List<Map<String, Any?>> =
        readableDatabase.rawQuery(
            "SELECT uid, played_at, artist, name, album, ms_played FROM plays WHERE synced = 0 ORDER BY played_at", null
        ).use { rows ->
            buildList {
                while (rows.moveToNext()) add(
                    mapOf(
                        "uid" to rows.getString(0), "played_at" to rows.getString(1), "artist" to rows.getString(2),
                        "name" to rows.getString(3), "album" to rows.getString(4), "ms_played" to rows.getLong(5),
                    )
                )
            }
        }

    /** Sent with this listening time: a time saved since then is still to be sent */
    fun markSynced(uid: String, ms: Long) {
        writableDatabase.execSQL("UPDATE plays SET synced = 1 WHERE uid = ? AND ms_played = ?", arrayOf<Any>(uid, ms))
    }
}
