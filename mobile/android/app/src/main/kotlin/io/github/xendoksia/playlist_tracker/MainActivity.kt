package io.github.xendoksia.playlist_tracker

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var wrapped: MethodChannel? = null

    /** The month of the summary notification the app was opened from, until Flutter takes it */
    private var tapped: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        // Not again when the app is opened from the recent apps with the notification's intent
        if (intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY == 0) {
            tapped = intent.getStringExtra(WrappedNotice.EXTRA)
        }
        super.onCreate(savedInstanceState)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        NowPlaying(applicationContext, flutterEngine.dartExecutor.binaryMessenger)
        wrapped = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "playlist_tracker/wrapped").apply {
            setMethodCallHandler { call, result ->
                when (call.method) {
                    "takeTapped" -> {
                        result.success(tapped)
                        tapped = null
                    }
                    // For the summary notification; Android asks only while the user has not said no for good
                    "askPermission" -> {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !WrappedNotice.allowed(context)) {
                            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
                        }
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
        }
    }

    /** The notification tapped while the app was open */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        val month = intent.getStringExtra(WrappedNotice.EXTRA) ?: return
        wrapped?.invokeMethod("tapped", month)
    }
}
