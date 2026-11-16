package io.github.xendoksia.playlist_tracker

import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_DEFAULT
import android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_DISABLED
import android.provider.Settings
import android.service.notification.NotificationListenerService

/**
 * Brings MediaListener back when Android stopped it: after the app's process was killed (or crashed) Android
 * keeps the notification access but does not always bind the listener again, and then nothing is recorded.
 * Checked when the app opens and every 15 minutes by a job Android runs while the app is closed, which also
 * sends the monthly summary notification (WrappedNotice).
 */
class ListenerKeeper : JobService() {
    companion object {
        private const val JOB_ID = 1

        fun hasAccess(context: Context): Boolean {
            val listener = ComponentName(context, MediaListener::class.java)
            val enabled = Settings.Secure.getString(context.contentResolver, "enabled_notification_listeners") ?: ""
            return enabled.split(':').any { ComponentName.unflattenFromString(it) == listener }
        }

        /**
         * Make Android bind the listener again, if it has access and is not running in this process. Switching it
         * off and on makes Android look at it again (requestRebind alone did nothing on a Honor phone).
         */
        fun revive(context: Context) {
            if (MediaListener.running || !hasAccess(context)) return
            val listener = ComponentName(context, MediaListener::class.java)
            val packages = context.packageManager
            for (state in listOf(COMPONENT_ENABLED_STATE_DISABLED, COMPONENT_ENABLED_STATE_DEFAULT)) {
                packages.setComponentEnabledSetting(listener, state, PackageManager.DONT_KILL_APP)
            }
            NotificationListenerService.requestRebind(listener)
        }

        fun schedule(context: Context) {
            val jobs = context.getSystemService(JobScheduler::class.java)
            if (jobs.getPendingJob(JOB_ID) != null) return
            jobs.schedule(
                JobInfo.Builder(JOB_ID, ComponentName(context, ListenerKeeper::class.java))
                    .setPeriodic(15 * 60_000L)
                    .setPersisted(true)
                    .build()
            )
        }
    }

    override fun onStartJob(params: JobParameters?): Boolean {
        revive(this)
        WrappedNotice.check(this)
        // Plays left unsent (the phone was offline, or a send failed) go when the network is there
        if (PlayStore(this).unsynced().isNotEmpty()) PlaySender.schedule(this)
        return false
    }

    override fun onStopJob(params: JobParameters?) = false
}
