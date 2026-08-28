package com.atlas.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AndroidTextToSpeechEngine @Inject constructor(
    @ApplicationContext private val context: Context
) : TextToSpeechEngine {

    private val _events = MutableSharedFlow<TextToSpeechEvent>(extraBufferCapacity = 16)
    override val events: SharedFlow<TextToSpeechEvent> = _events.asSharedFlow()

    private val speaking = AtomicBoolean(false)
    private val utteranceCounter = AtomicInteger(0)
    private var pendingText: String? = null
    private var isReady = false

    private val tts: TextToSpeech = TextToSpeech(context) { status -> onTtsInit(status) }

    init {
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {
                speaking.set(true)
                _events.tryEmit(TextToSpeechEvent.Started)
            }

            override fun onDone(utteranceId: String?) {
                speaking.set(false)
                _events.tryEmit(TextToSpeechEvent.Completed)
            }

            override fun onError(utteranceId: String?) {
                speaking.set(false)
                _events.tryEmit(TextToSpeechEvent.Error("Text-to-speech playback failed."))
            }
        })
    }

    private fun onTtsInit(status: Int) {
        isReady = status == TextToSpeech.SUCCESS
        if (isReady) {
            tts.language = Locale.getDefault()
            pendingText?.let { speak(it) }
            pendingText = null
        } else {
            _events.tryEmit(TextToSpeechEvent.Error("Text-to-speech engine failed to initialize."))
        }
    }

    override fun isSpeaking(): Boolean = speaking.get()

    override fun speak(text: String, interrupt: Boolean) {
        if (text.isBlank()) return

        if (!isReady) {
            pendingText = text
            return
        }

        val queueMode = if (interrupt) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD
        val utteranceId = "atlas-utterance-${utteranceCounter.incrementAndGet()}"
        tts.speak(text, queueMode, null, utteranceId)
    }

    override fun stop() {
        tts.stop()
        speaking.set(false)
    }

    override fun setSpeechRate(rate: Float) {
        tts.setSpeechRate(rate)
    }

    override fun shutdown() {
        tts.stop()
        tts.shutdown()
    }
}
