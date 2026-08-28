package com.atlas

import com.atlas.voice.AudioOutputRoute
import com.atlas.voice.AudioSessionManager
import com.atlas.voice.SpeechToTextEngine
import com.atlas.voice.SpeechToTextEvent
import com.atlas.voice.TextToSpeechEngine
import com.atlas.voice.TextToSpeechEvent
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Phase 8 stabilization: test doubles for VoiceManager's three dependencies,
 * enabling VoiceManagerTest/ConversationAudioControllerTest to exist at all
 * without Robolectric or an instrumented test. See the doc comment on the
 * AudioSessionManager interface for why AudioSessionManager specifically
 * was refactored to make FakeAudioSessionManager possible.
 */
class FakeSpeechToTextEngine : SpeechToTextEngine {
    private val _events = MutableSharedFlow<SpeechToTextEvent>(extraBufferCapacity = 16)
    override val events: SharedFlow<SpeechToTextEvent> = _events.asSharedFlow()

    var available = true
    var startListeningCalled = false
    var stopListeningCalled = false
    var cancelCalled = false
    var destroyCalled = false

    override fun isAvailable(): Boolean = available
    override fun startListening() { startListeningCalled = true }
    override fun stopListening() { stopListeningCalled = true }
    override fun cancel() { cancelCalled = true }
    override fun destroy() { destroyCalled = true }

    fun emit(event: SpeechToTextEvent) = _events.tryEmit(event)
}

class FakeTextToSpeechEngine : TextToSpeechEngine {
    private val _events = MutableSharedFlow<TextToSpeechEvent>(extraBufferCapacity = 16)
    override val events: SharedFlow<TextToSpeechEvent> = _events.asSharedFlow()

    var speaking = false
    var lastSpokenText: String? = null
    var stopCalled = false
    var shutdownCalled = false

    override fun isSpeaking(): Boolean = speaking
    override fun speak(text: String, interrupt: Boolean) { lastSpokenText = text }
    override fun stop() { stopCalled = true }
    override fun setSpeechRate(rate: Float) {}
    override fun shutdown() { shutdownCalled = true }

    fun emit(event: TextToSpeechEvent) = _events.tryEmit(event)
}

class FakeAudioSessionManager : AudioSessionManager {
    var focusGranted = true
    var requestFocusCalled = false
    var abandonFocusCalled = false
    var outputRoute = AudioOutputRoute.SPEAKER
    private var onFocusLost: (() -> Unit)? = null

    override fun requestFocus(onFocusLost: () -> Unit): Boolean {
        requestFocusCalled = true
        this.onFocusLost = onFocusLost
        return focusGranted
    }

    override fun abandonFocus() { abandonFocusCalled = true }
    override fun currentOutputRoute(): AudioOutputRoute = outputRoute

    /** Test helper to simulate the system taking audio focus away mid-session. */
    fun simulateFocusLost() = onFocusLost?.invoke()
}
