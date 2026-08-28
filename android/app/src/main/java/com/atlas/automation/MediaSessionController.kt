package com.atlas.automation

import android.content.ComponentName
import android.content.Context
import android.media.AudioManager
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation - Media Session Controller module.
 *
 * Implements play / pause / next / previous / volume / now-playing using
 * only the official android.media.session.MediaSessionManager and
 * android.media.AudioManager APIs.
 *
 * Notification Listener access is what actually gates this, not a
 * separate permission - MediaSessionManager.getActiveSessions() requires
 * the caller to be an enabled NotificationListenerService (or hold
 * MEDIA_CONTENT_CONTROL, a signature permission apps can't hold), so this
 * throws SecurityException until the user enables the same "Notification
 * Listener" toggle in Permission Center that AtlasNotificationListenerService
 * uses. That coupling is a real platform constraint, not a design choice
 * made here - see docs/Phase8_KnownLimitations.md.
 */
interface MediaSessionControllerApi {
    suspend fun play(): AutomationResult
    suspend fun pause(): AutomationResult
    suspend fun next(): AutomationResult
    suspend fun previous(): AutomationResult
    suspend fun volumeUp(): AutomationResult
    suspend fun volumeDown(): AutomationResult
    suspend fun nowPlaying(): AutomationResult
}

@Singleton
class AndroidMediaSessionController @Inject constructor(
    @ApplicationContext private val context: Context
) : MediaSessionControllerApi {

    private val audioManager: AudioManager by lazy {
        context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    }

    private fun activeController(): MediaController? {
        val sessionManager = context.getSystemService(Context.MEDIA_SESSION_SERVICE) as MediaSessionManager
        val listenerComponent = ComponentName(context, AtlasNotificationListenerService::class.java)
        val sessions = try {
            sessionManager.getActiveSessions(listenerComponent)
        } catch (e: SecurityException) {
            return null
        }
        // Prefer a session that's actually playing over one that's merely
        // present (e.g. a paused session left behind from an earlier app).
        return sessions.firstOrNull { it.playbackState?.state == PlaybackState.STATE_PLAYING }
            ?: sessions.firstOrNull()
    }

    override suspend fun play(): AutomationResult {
        val controller = activeController() ?: return noSession()
        controller.transportControls.play()
        return AutomationResult.ok("Resuming playback.")
    }

    override suspend fun pause(): AutomationResult {
        val controller = activeController() ?: return noSession()
        controller.transportControls.pause()
        return AutomationResult.ok("Paused.")
    }

    override suspend fun next(): AutomationResult {
        val controller = activeController() ?: return noSession()
        controller.transportControls.skipToNext()
        return AutomationResult.ok("Skipped to the next track.")
    }

    override suspend fun previous(): AutomationResult {
        val controller = activeController() ?: return noSession()
        controller.transportControls.skipToPrevious()
        return AutomationResult.ok("Went back to the previous track.")
    }

    override suspend fun volumeUp(): AutomationResult {
        audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
        return AutomationResult.ok("Turned the volume up.")
    }

    override suspend fun volumeDown(): AutomationResult {
        audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
        return AutomationResult.ok("Turned the volume down.")
    }

    override suspend fun nowPlaying(): AutomationResult {
        val controller = activeController() ?: return noSession()
        val metadata = controller.metadata
            ?: return AutomationResult.ok("Nothing appears to be playing right now.")
        val title = metadata.getString(MediaMetadata.METADATA_KEY_TITLE)
        val artist = metadata.getString(MediaMetadata.METADATA_KEY_ARTIST)
        val summary = when {
            title != null && artist != null -> "Now playing: $title by $artist."
            title != null -> "Now playing: $title."
            else -> "Something's playing, but it didn't report a title."
        }
        return AutomationResult.ok(
            summary,
            details = buildMap {
                title?.let { put("title", it) }
                artist?.let { put("artist", it) }
            }
        )
    }

    private fun noSession(): AutomationResult = AutomationResult.failed(
        "No active media session was found. Make sure something is playing, and that Notification Listener access is enabled in Permission Center (media control relies on the same permission)."
    )
}
