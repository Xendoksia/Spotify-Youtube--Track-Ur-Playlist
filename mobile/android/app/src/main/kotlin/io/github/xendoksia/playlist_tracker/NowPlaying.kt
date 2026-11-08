package io.github.xendoksia.playlist_tracker

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

/**
 * What the Spotify app plays on the phone, read from its media session (the one its notification shows),
 * sent to Flutter as it changes. Needs notification access for MediaListener.
 */
class NowPlaying(private val context: Context, messenger: BinaryMessenger) : EventChannel.StreamHandler {
    companion object {
        const val SPOTIFY = "com.spotify.music"
    }

    private val listener = ComponentName(context, MediaListener::class.java)
    private val sessions = context.getSystemService(MediaSessionManager::class.java)
    private val main = Handler(Looper.getMainLooper())
    private var events: EventChannel.EventSink? = null
    private var controller: MediaController? = null
    private var listening = false

    private val sessionsChanged = MediaSessionManager.OnActiveSessionsChangedListener { follow(it) }

    private val callback = object : MediaController.Callback() {
        override fun onMetadataChanged(metadata: MediaMetadata?) = send()
        override fun onPlaybackStateChanged(state: PlaybackState?) = send()
        override fun onSessionDestroyed() = follow(null)
    }

    init {
        MethodChannel(messenger, "playlist_tracker/now_playing").setMethodCallHandler { call, result ->
            when (call.method) {
                "hasAccess" -> result.success(hasAccess())
                "openSettings" -> {
                    context.startActivity(
                        Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    )
                    result.success(null)
                }
                // After coming back from the settings, where access may have just been given
                "restart" -> {
                    stop()
                    if (events != null) start()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        EventChannel(messenger, "playlist_tracker/now_playing/events").setStreamHandler(this)
    }

    private fun hasAccess(): Boolean {
        val enabled = Settings.Secure.getString(context.contentResolver, "enabled_notification_listeners") ?: ""
        return enabled.split(':').any { ComponentName.unflattenFromString(it) == listener }
    }

    override fun onListen(arguments: Any?, sink: EventChannel.EventSink?) {
        events = sink
        start()
    }

    override fun onCancel(arguments: Any?) {
        stop()
        events = null
    }

    private fun start() {
        if (listening || !hasAccess()) {
            send()
            return
        }
        try {
            sessions.addOnActiveSessionsChangedListener(sessionsChanged, listener, main)
            listening = true
            follow(sessions.getActiveSessions(listener))
        } catch (_: SecurityException) {
            // Access was taken back between the check and here
            send()
        }
    }

    private fun stop() {
        if (listening) sessions.removeOnActiveSessionsChangedListener(sessionsChanged)
        listening = false
        controller?.unregisterCallback(callback)
        controller = null
    }

    /** Watch Spotify's session among the active ones, if it has one */
    private fun follow(active: List<MediaController>?) {
        val spotify = active?.firstOrNull { it.packageName == SPOTIFY }
        if (spotify?.sessionToken != controller?.sessionToken) {
            controller?.unregisterCallback(callback)
            controller = spotify
            spotify?.registerCallback(callback, main)
        }
        send()
    }

    private fun send() {
        events?.success(snapshot())
    }

    /** The song and where it is, or null when Spotify plays nothing (or there is no access) */
    private fun snapshot(): Map<String, Any?>? {
        val playing = controller ?: return null
        val metadata = playing.metadata ?: return null
        val state = playing.playbackState
        val title = metadata.getString(MediaMetadata.METADATA_KEY_TITLE) ?: return null
        val position = state?.position?.takeIf { it >= 0 && state.state != PlaybackState.STATE_NONE }
        // The position was read at lastPositionUpdateTime (time since boot); as wall clock time for Dart
        val positionAt = state?.lastPositionUpdateTime?.let {
            System.currentTimeMillis() - (SystemClock.elapsedRealtime() - it)
        }
        return mapOf(
            "app" to playing.packageName,
            "title" to title,
            "artist" to (metadata.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: ""),
            "album" to (metadata.getString(MediaMetadata.METADATA_KEY_ALBUM) ?: ""),
            "duration" to metadata.getLong(MediaMetadata.METADATA_KEY_DURATION).takeIf { it > 0 },
            "position" to position,
            "positionAt" to positionAt,
            "speed" to (state?.playbackSpeed?.toDouble() ?: 1.0),
            "playing" to (state?.state == PlaybackState.STATE_PLAYING),
        )
    }
}
