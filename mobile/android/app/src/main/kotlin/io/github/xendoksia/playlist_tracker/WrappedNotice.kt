package io.github.xendoksia.playlist_tracker

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

/**
 * "Your October in review is ready": on the first days of a month, a notification for the summary of the month
 * before (wrapped_screen.dart), while the app is closed. Checked by ListenerKeeper's job every 15 minutes; tapping
 * it opens the app on the summary (MainActivity).
 *
 * Sent once a month, only when the month had plays and the summary was not seen yet. What it reads Flutter keeps
 * in its shared preferences: WRAPPED_SHOWN (the month last seen), PLAY_MONTHS (the months with plays when the app
 * was last open) and LANGUAGE.
 */
object WrappedNotice {
    /** The month of the summary ("2026-10") in the intent of a tapped notification */
    const val EXTRA = "wrapped_month"

    /** As wrappedDays in Flutter; on the first day not before this hour, not to wake anyone at midnight */
    private val DAYS = setOf(1, 2)
    private const val FROM_HOUR = 10
    private const val CHANNEL = "wrapped"
    private const val ID = 2

    fun check(context: Context) {
        val now = Calendar.getInstance()
        val day = now.get(Calendar.DAY_OF_MONTH)
        if (day !in DAYS || (day == 1 && now.get(Calendar.HOUR_OF_DAY) < FROM_HOUR)) return
        val end = (now.clone() as Calendar).apply {
            set(Calendar.DAY_OF_MONTH, 1)
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val start = (end.clone() as Calendar).apply { add(Calendar.MONTH, -1) }
        val month = String.format(Locale.US, "%04d-%02d", start.get(Calendar.YEAR), start.get(Calendar.MONTH) + 1)

        val prefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        if (prefs.getString("flutter.WRAPPED_SHOWN", null) == month) return
        if (prefs.getString("flutter.WRAPPED_NOTIFIED", null) == month) return
        val played = month in (prefs.getString("flutter.PLAY_MONTHS", null) ?: "").split(',') ||
            PlayStore(context).hasPlays(PlayRecorder.utc(start.timeInMillis), PlayRecorder.utc(end.timeInMillis))
        if (!played || !allowed(context)) return

        val language = prefs.getString("flutter.LANGUAGE", null) ?: Locale.getDefault().language
        val turkish = language == "tr"
        val locale = if (turkish) Locale.forLanguageTag("tr") else Locale.ENGLISH
        val name = SimpleDateFormat("LLLL", locale).format(start.time).replaceFirstChar { it.titlecase(locale) }
        val title = if (turkish) "$name özetin hazır" else "Your $name in review is ready"
        val text = if (turkish) "Ayın şarkısı, sanatçısı ve daha fazlası. Görmek için dokun."
        else "The song and artist of the month and more. Tap to see it."

        val notifications = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            notifications.createNotificationChannel(
                NotificationChannel(
                    CHANNEL, if (turkish) "Aylık özet" else "Monthly summary", NotificationManager.IMPORTANCE_DEFAULT
                )
            )
        }
        val open = PendingIntent.getActivity(
            context, 0,
            Intent(context, MainActivity::class.java).putExtra(EXTRA, month)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(context, CHANNEL)
        else @Suppress("DEPRECATION") Notification.Builder(context)
        notifications.notify(
            ID,
            builder.setSmallIcon(R.drawable.ic_notification)
                .setColor(0xFF1AA34A.toInt())
                .setContentTitle(title)
                .setContentText(text)
                .setContentIntent(open)
                .setAutoCancel(true)
                .build()
        )
        prefs.edit().putString("flutter.WRAPPED_NOTIFIED", month).apply()
    }

    fun allowed(context: Context) = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
        context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
}
