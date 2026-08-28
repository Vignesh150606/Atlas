package com.atlas.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Wraps android.speech.SpeechRecognizer. Every method here must be called
 * from the main thread - that's an Android platform requirement for
 * SpeechRecognizer, not a choice made here. In practice this is satisfied
 * automatically because the only caller is VoiceManager, driven from
 * viewModelScope (Dispatchers.Main.immediate by default).
 */
@Singleton
class AndroidSpeechToTextEngine @Inject constructor(
    @ApplicationContext private val context: Context
) : SpeechToTextEngine {

    private val _events = MutableSharedFlow<SpeechToTextEvent>(extraBufferCapacity = 16)
    override val events: SharedFlow<SpeechToTextEvent> = _events.asSharedFlow()

    private var recognizer: SpeechRecognizer? = null

    override fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    override fun startListening() {
        if (!isAvailable()) {
            _events.tryEmit(SpeechToTextEvent.Error("Speech recognition isn't available on this device.", recoverable = false))
            return
        }

        val activeRecognizer = recognizer ?: SpeechRecognizer.createSpeechRecognizer(context).also {
            it.setRecognitionListener(listener)
            recognizer = it
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        }
        activeRecognizer.startListening(intent)
    }

    override fun stopListening() {
        recognizer?.stopListening()
    }

    override fun cancel() {
        recognizer?.cancel()
    }

    override fun destroy() {
        recognizer?.destroy()
        recognizer = null
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            _events.tryEmit(SpeechToTextEvent.ReadyForSpeech)
        }

        override fun onBeginningOfSpeech() {
            _events.tryEmit(SpeechToTextEvent.BeginningOfSpeech)
        }

        override fun onRmsChanged(rmsdB: Float) {
            _events.tryEmit(SpeechToTextEvent.RmsChanged(rmsdB))
        }

        override fun onBufferReceived(buffer: ByteArray?) {
            // Raw audio buffer - unused. A future streaming engine (e.g.
            // Whisper) would consume this instead of onResults; kept as a
            // no-op here rather than removed, so the interface boundary
            // this class sits behind doesn't need to change later.
        }

        override fun onEndOfSpeech() {
            _events.tryEmit(SpeechToTextEvent.EndOfSpeech)
        }

        override fun onError(error: Int) {
            val (message, recoverable) = describeError(error)
            _events.tryEmit(SpeechToTextEvent.Error(message, recoverable))
        }

        override fun onResults(results: Bundle?) {
            val text = results
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
                ?.trim()
            if (!text.isNullOrEmpty()) {
                _events.tryEmit(SpeechToTextEvent.FinalResult(text))
            } else {
                _events.tryEmit(SpeechToTextEvent.Error("Didn't catch that - no speech recognized.", recoverable = true))
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val text = partialResults
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
            if (!text.isNullOrEmpty()) {
                _events.tryEmit(SpeechToTextEvent.PartialResult(text))
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {
            // Reserved by the platform API for vendor-specific events - no
            // documented standard events to handle here.
        }
    }

    private fun describeError(code: Int): Pair<String, Boolean> = when (code) {
        SpeechRecognizer.ERROR_NO_MATCH -> "Didn't catch that - try again." to true
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech detected." to true
        SpeechRecognizer.ERROR_NETWORK -> "Network error during speech recognition." to true
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Speech recognition timed out." to true
        SpeechRecognizer.ERROR_AUDIO -> "Audio recording error." to true
        SpeechRecognizer.ERROR_SERVER -> "Speech recognition server error." to true
        SpeechRecognizer.ERROR_CLIENT -> "Speech recognition was cancelled." to true
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Speech recognizer is busy." to true
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission is required." to false
        else -> "Speech recognition error (code $code)." to true
    }
}
