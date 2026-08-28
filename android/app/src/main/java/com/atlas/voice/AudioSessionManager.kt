package com.atlas.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

enum class AudioOutputRoute {
    SPEAKER,
    WIRED_HEADSET,
    BLUETOOTH
}

/**
 * Phase 8 stabilization: extracted as an interface (mirroring
 * SpeechToTextEngine/TextToSpeechEngine, VoiceManager's other two
 * dependencies) so VoiceManager and ConversationAudioController - the two
 * classes involved in the Retry/clearError() bug this phase fixed - can
 * actually be unit tested with a fake instead of needing Robolectric or an
 * instrumented test just to exercise state-machine wiring that has nothing
 * to do with real audio hardware. See AndroidAudioSessionManager for the
 * real implementation and FakeAudioSessionManager (test sources) for the
 * fake used by VoiceManagerTest/ConversationAudioControllerTest.
 */
interface AudioSessionManager {
    /**
     * Requests transient audio focus for one listen-or-speak turn.
     * [onFocusLost] fires when something else takes focus (e.g. an
     * incoming call) - the voice pipeline should treat that as "stop and
     * go back to idle," not try to fight for focus back.
     */
    fun requestFocus(onFocusLost: () -> Unit): Boolean
    fun abandonFocus()
    fun currentOutputRoute(): AudioOutputRoute
}

/**
 * Wraps AudioManager for the pieces the voice pipeline actually needs:
 * requesting/abandoning transient audio focus around a listen-or-speak
 * turn, and knowing what the current output route is (speaker vs wired
 * headset vs Bluetooth) so the UI can reflect it if useful. This is audio
 * *routing* awareness only - not Bluetooth device management/pairing,
 * which is out of scope for voice mode.
 */
@Singleton
class AndroidAudioSessionManager @Inject constructor(
    @ApplicationContext private val context: Context
) : AudioSessionManager {
    private val audioManager: AudioManager =
        context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    private var focusRequest: AudioFocusRequest? = null

    override fun requestFocus(onFocusLost: () -> Unit): Boolean {
        val attributes = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ASSISTANT)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            .build()

        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            .setAudioAttributes(attributes)
            .setOnAudioFocusChangeListener { focusChange ->
                when (focusChange) {
                    AudioManager.AUDIOFOCUS_LOSS,
                    AudioManager.AUDIOFOCUS_LOSS_TRANSIENT,
                    AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> onFocusLost()
                }
            }
            .build()

        val granted = audioManager.requestAudioFocus(request) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        if (granted) {
            focusRequest = request
        }
        return granted
    }

    override fun abandonFocus() {
        focusRequest?.let { audioManager.abandonAudioFocusRequest(it) }
        focusRequest = null
    }

    override fun currentOutputRoute(): AudioOutputRoute {
        val outputs = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        val hasBluetooth = outputs.any {
            it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP || it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
        }
        val hasWired = outputs.any {
            it.type == AudioDeviceInfo.TYPE_WIRED_HEADSET || it.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES
        }
        return when {
            hasBluetooth -> AudioOutputRoute.BLUETOOTH
            hasWired -> AudioOutputRoute.WIRED_HEADSET
            else -> AudioOutputRoute.SPEAKER
        }
    }
}
