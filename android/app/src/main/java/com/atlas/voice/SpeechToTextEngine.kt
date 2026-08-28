package com.atlas.voice

import kotlinx.coroutines.flow.SharedFlow

/**
 * Events emitted while listening. Deliberately mirrors the shape of
 * Android's RecognitionListener callbacks (readiness, partial/final
 * results, amplitude, error) rather than Android's actual types, so a
 * future engine (e.g. an on-device Whisper implementation) can emit the
 * same events without SpeechToTextEngine callers ever depending on
 * android.speech.* directly.
 */
sealed class SpeechToTextEvent {
    object ReadyForSpeech : SpeechToTextEvent()
    object BeginningOfSpeech : SpeechToTextEvent()
    data class RmsChanged(val rmsDb: Float) : SpeechToTextEvent()
    data class PartialResult(val text: String) : SpeechToTextEvent()
    data class FinalResult(val text: String) : SpeechToTextEvent()
    object EndOfSpeech : SpeechToTextEvent()
    data class Error(val message: String, val recoverable: Boolean) : SpeechToTextEvent()
}

/**
 * Speech-to-text abstraction. [AndroidSpeechToTextEngine] is the only
 * implementation today (on-device Android SpeechRecognizer); the interface
 * exists so a streaming Whisper engine can be swapped in later without
 * touching VoiceManager or anything above it.
 */
interface SpeechToTextEngine {
    val events: SharedFlow<SpeechToTextEvent>

    fun isAvailable(): Boolean
    fun startListening()
    fun stopListening()
    fun cancel()
    fun destroy()
}
