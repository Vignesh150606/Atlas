package com.atlas.voice

import kotlinx.coroutines.flow.SharedFlow

sealed class TextToSpeechEvent {
    object Started : TextToSpeechEvent()
    object Completed : TextToSpeechEvent()
    data class Error(val message: String) : TextToSpeechEvent()
}

/**
 * Text-to-speech abstraction. [AndroidTextToSpeechEngine] is the only
 * implementation today (on-device Android TextToSpeech); the interface
 * exists so a future Piper (on-device neural TTS) implementation can be
 * swapped in without touching VoiceManager or anything above it.
 */
interface TextToSpeechEngine {
    val events: SharedFlow<TextToSpeechEvent>

    /** true while audio is actively being spoken. */
    fun isSpeaking(): Boolean

    /** interrupt=true stops whatever is currently speaking/queued first (barge-in). */
    fun speak(text: String, interrupt: Boolean = false)
    fun stop()
    fun setSpeechRate(rate: Float)
    fun shutdown()
}
