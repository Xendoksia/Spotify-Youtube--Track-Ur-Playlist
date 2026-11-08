package io.github.xendoksia.playlist_tracker

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        NowPlaying(applicationContext, flutterEngine.dartExecutor.binaryMessenger)
    }
}
