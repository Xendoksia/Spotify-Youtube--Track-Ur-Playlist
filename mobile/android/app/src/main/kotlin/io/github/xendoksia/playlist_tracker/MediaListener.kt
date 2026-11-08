package io.github.xendoksia.playlist_tracker

import android.service.notification.NotificationListenerService

/**
 * Does nothing itself: with notification access granted to it, Android lets the app read the phone's media
 * sessions (what Spotify plays), see NowPlaying.
 */
class MediaListener : NotificationListenerService()
