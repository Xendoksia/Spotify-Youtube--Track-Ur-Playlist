package io.github.xendoksia.playlist_tracker

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

/**
 * "Your October in review is ready": on the first days of a month, a notification for the summary of the month
 * before (wrapped_screen.dart), and in January one for the year before too, while the app is closed. Checked by
 * ListenerKeeper's job every 15 minutes; tapping it opens the app on the summary (MainActivity).
 *
 * Sent once each, only when the month (year) had plays and its summary was not seen yet. What it reads Flutter
 * keeps in its shared preferences: WRAPPED_SHOWN / WRAPPED_YEAR_SHOWN (the month / year last seen), PLAY_MONTHS
 * (the months with plays when the app was last open) and LANGUAGE.
 */
object WrappedNotice {
    /** The summary's month ("2026-10") or year ("2026") in the intent of a tapped notification */
    const val EXTRA = "wrapped_month"

    /** As wrappedDays in Flutter; on the first day not before this hour, not to wake anyone at midnight */
    private val DAYS = setOf(1, 2)
    private const val FROM_HOUR = 10
    private const val CHANNEL = "wrapped"

    /** A month's or a year's summary: its key, where it starts and ends, and the notification's id */
    private class Summary(val year: Boolean, val start: Calendar, val end: Calendar) {
        val key: String = if (year) "${start.get(Calendar.YEAR)}"
        else String.format(Locale.US, "%04d-%02d", start.get(Calendar.YEAR), start.get(Calendar.MONTH) + 1)
        val id = if (year) 3 else 2
        val setting = if (year) "WRAPPED_YEAR" else "WRAPPED"
    }

    fun check(context: Context) {
        val now = Calendar.getInstance()
        val day = now.get(Calendar.DAY_OF_MONTH)
        if (day !in DAYS || (day == 1 && now.get(Calendar.HOUR_OF_DAY) < FROM_HOUR)) return
        if (!allowed(context)) return
        val thisMonth = (now.clone() as Calendar).apply {
            set(Calendar.DAY_OF_MONTH, 1)
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val summaries = buildList {
            if (now.get(Calendar.MONTH) == Calendar.JANUARY) {
                add(Summary(true, (thisMonth.clone() as Calendar).apply { add(Calendar.YEAR, -1) }, thisMonth))
            }
            add(Summary(false, (thisMonth.clone() as Calendar).apply { add(Calendar.MONTH, -1) }, thisMonth))
        }
        val prefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        for (summary in summaries) notify(context, prefs, summary)
    }

    private fun notify(context: Context, prefs: SharedPreferences, summary: Summary) {
        val key = summary.key
        if (prefs.getString("flutter.${summary.setting}_SHOWN", null) == key) return
        if (prefs.getString("flutter.${summary.setting}_NOTIFIED", null) == key) return
        val months = (prefs.getString("flutter.PLAY_MONTHS", null) ?: "").split(',')
        val played = (if (summary.year) months.any { it.startsWith("$key-") } else key in months) ||
            PlayStore(context).hasPlays(
                PlayRecorder.utc(summary.start.timeInMillis), PlayRecorder.utc(summary.end.timeInMillis)
            )
        if (!played) return

        val language = prefs.getString("flutter.LANGUAGE", null) ?: Locale.getDefault().language
        val turkish = language == "tr"
        val locale = if (turkish) Locale.forLanguageTag("tr") else Locale.ENGLISH
        val name = if (summary.year) key
        else SimpleDateFormat("LLLL", locale).format(summary.start.time).replaceFirstChar { it.titlecase(locale) }
        val title = if (turkish) "$name özetin hazır" else "Your $name in review is ready"
        val text = when {
            turkish && summary.year -> "Yılın şarkısı, sanatçısı ve daha fazlası. Görmek için dokun."
            turkish -> "Ayın şarkısı, sanatçısı ve daha fazlası. Görmek için dokun."
            summary.year -> "The song and artist of the year and more. Tap to see it."
            else -> "The song and artist of the month and more. Tap to see it."
        }

        val notifications = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            notifications.createNotificationChannel(
                NotificationChannel(
                    CHANNEL, if (turkish) "Aylık özet" else "Monthly summary", NotificationManager.IMPORTANCE_DEFAULT
                )
            )
        }
        // Its own request code each, or the year's intent would be replaced by the month's
        val open = PendingIntent.getActivity(
            context, summary.id,
            Intent(context, MainActivity::class.java).putExtra(EXTRA, key)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(context, CHANNEL)
        else @Suppress("DEPRECATION") Notification.Builder(context)
        notifications.notify(
            summary.id,
            builder.setSmallIcon(R.drawable.ic_notification)
                .setColor(0xFF1AA34A.toInt())
                .setContentTitle(title)
                .setContentText(text)
                .setContentIntent(open)
                .setAutoCancel(true)
                .build()
        )
        prefs.edit().putString("flutter.${summary.setting}_NOTIFIED", key).apply()
    }

    /** The summary of key ("2026-10" or "2026") was seen in the app */
    fun cancel(context: Context, key: String) {
        context.getSystemService(NotificationManager::class.java).cancel(if ('-' in key) 2 else 3)
    }

    fun allowed(context: Context) = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
        context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
}
