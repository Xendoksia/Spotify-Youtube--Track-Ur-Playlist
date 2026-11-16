package io.github.xendoksia.playlist_tracker

import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import io.flutter.FlutterInjector
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.dart.DartExecutor
import io.flutter.plugin.common.MethodChannel

/**
 * Sends the plays recorded on the phone (PlayStore) to Supabase while the app is closed, so the desktop app sees
 * them without the phone's app being opened. Scheduled when a play is stored or its time grows, it waits a few
 * minutes (a song or two go together) and for the network, then runs the app's own sending code (sendPlays in
 * Dart, entry point backgroundSend) in a Flutter engine without a screen, with the session the app keeps.
 *
 * Not while the app's screen is up: that engine holds the session too and sends the plays itself, and two
 * engines renewing the same session at once could make Supabase end it.
 */
class PlaySender : JobService() {
    companion object {
        private const val JOB_ID = 2
        private const val WAIT_MS = 3 * 60_000L
        // Android stops a job after 10 minutes; a send that hangs gives up well before
        private const val GIVE_UP_MS = 2 * 60_000L

        /** Engines of the app's screen alive in this process (MainActivity) */
        @Volatile
        var screens = 0

        fun schedule(context: Context) {
            val jobs = context.getSystemService(JobScheduler::class.java)
            if (jobs.getPendingJob(JOB_ID) != null) return
            jobs.schedule(
                JobInfo.Builder(JOB_ID, ComponentName(context, PlaySender::class.java))
                    .setMinimumLatency(WAIT_MS)
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                    .setBackoffCriteria(5 * 60_000L, JobInfo.BACKOFF_POLICY_EXPONENTIAL)
                    .setPersisted(true)
                    .build()
            )
        }
    }

    private val main = Handler(Looper.getMainLooper())
    private var engine: FlutterEngine? = null
    private var params: JobParameters? = null

    override fun onStartJob(params: JobParameters?): Boolean {
        if (screens > 0 || PlayStore(this).unsynced().isEmpty()) return false
        this.params = params
        val engine = FlutterEngine(applicationContext).also { engine = it }
        // The same channel the app reads the plays from
        NowPlaying(applicationContext, engine.dartExecutor.binaryMessenger)
        MethodChannel(engine.dartExecutor.binaryMessenger, "playlist_tracker/background").setMethodCallHandler { call, result ->
            result.success(null)
            // "sent" with how many, or "failed": tried again later
            Log.i("PlaySender", "${call.method} ${call.arguments ?: ""}")
            finish(failed = call.method == "failed")
        }
        val loader = FlutterInjector.instance().flutterLoader()
        loader.startInitialization(applicationContext)
        loader.ensureInitializationComplete(applicationContext, null)
        engine.dartExecutor.executeDartEntrypoint(
            DartExecutor.DartEntrypoint(loader.findAppBundlePath(), "backgroundSend")
        )
        main.postDelayed({ finish(failed = true) }, GIVE_UP_MS)
        return true
    }

    private fun finish(failed: Boolean) {
        val done = params ?: return
        params = null
        main.removeCallbacksAndMessages(null)
        engine?.destroy()
        engine = null
        jobFinished(done, failed)
    }

    override fun onStopJob(params: JobParameters?): Boolean {
        this.params = null
        main.removeCallbacksAndMessages(null)
        engine?.destroy()
        engine = null
        return true
    }
}
