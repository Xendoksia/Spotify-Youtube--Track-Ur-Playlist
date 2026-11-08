package io.github.xendoksia.playlist_tracker

import android.content.ComponentName
import android.service.notification.NotificationListenerService

/**
 * With notification access granted to it, Android lets the app read the phone's media sessions (what Spotify
 * plays, see NowPlaying) and keeps this service running while the app is closed, so it records the plays.
 *
 * The recorder starts with the service, which is all reading the sessions needs.
 */
class MediaListener : NotificationListenerService() {
    companion object {
        /** Running in this process (ListenerKeeper binds it again when it is not) */
        @Volatile
        var running = false
    }

    private var recorder: PlayRecorder? = null

    override fun onCreate() {
        super.onCreate()
        running = true
        ListenerKeeper.schedule(this)
        recorder = PlayRecorder(this, ComponentName(this, MediaListener::class.java)).also { it.start() }
    }

    override fun onDestroy() {
        running = false
        recorder?.stop()
        recorder = null
        super.onDestroy()
    }
}
