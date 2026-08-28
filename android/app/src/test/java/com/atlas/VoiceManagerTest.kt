package com.atlas

import com.atlas.voice.SpeechToTextEvent
import com.atlas.voice.TextToSpeechEvent
import com.atlas.voice.VoiceManager
import com.atlas.voice.VoiceState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/**
 * Phase 8 stabilization. VoiceManager.init{} launches coroutines on
 * Dispatchers.Main.immediate, so - same as ChatViewModelTest/
 * MemoryViewModelTest - Dispatchers.setMain(...) must be installed before
 * construction or this throws immediately in a plain JVM test.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class VoiceManagerTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var stt: FakeSpeechToTextEngine
    private lateinit var tts: FakeTextToSpeechEngine
    private lateinit var audio: FakeAudioSessionManager
    private lateinit var manager: VoiceManager

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        stt = FakeSpeechToTextEngine()
        tts = FakeTextToSpeechEngine()
        audio = FakeAudioSessionManager()
        manager = VoiceManager(stt, tts, audio)
        // VoiceManager.init{} launches `speechToText.events.collect{...}` /
        // `textToSpeech.events.collect{...}` on Dispatchers.Main.immediate,
        // backed here by StandardTestDispatcher - that launch is only
        // *scheduled*, not run, until the scheduler is pumped. Without this,
        // those collectors haven't subscribed yet by the time a test calls
        // stt.emit()/tts.emit(), and since both fakes' SharedFlows use the
        // default replay = 0, a tryEmit() with nobody subscribed is dropped
        // permanently - a later advanceUntilIdle() does not retroactively
        // deliver it. This one-time pump lets the collectors subscribe
        // before any test gets a chance to emit.
        testDispatcher.scheduler.advanceUntilIdle()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testStartListeningRequestsFocusAndTransitionsToListening() {
        manager.startListening()
        assertTrue(audio.requestFocusCalled)
        assertTrue(stt.startListeningCalled)
        assertEquals(VoiceState.LISTENING, manager.state.value)
    }

    @Test
    fun testStartListeningWithoutFocusStaysIdleAndEmitsError() {
        audio.focusGranted = false
        manager.startListening()
        assertEquals(VoiceState.IDLE, manager.state.value)
        assertFalse(stt.startListeningCalled)
    }

    @Test
    fun testSttErrorTransitionsToErrorState() {
        manager.startListening()
        stt.emit(SpeechToTextEvent.Error("mic failure", recoverable = true))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.ERROR, manager.state.value)
    }

    // --- The regression test for this phase's stabilization fix ---------

    @Test
    fun testClearErrorResetsErrorStateBackToIdle() {
        manager.startListening()
        stt.emit(SpeechToTextEvent.Error("mic failure", recoverable = true))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.ERROR, manager.state.value)

        manager.clearError()

        assertEquals(
            "clearError() must reset VoiceManager's own state machine out of ERROR, or the Voice screen's Retry button stays stuck forever (see clearError() doc comment)",
            VoiceState.IDLE,
            manager.state.value
        )
    }

    @Test
    fun testClearErrorIsANoOpOutsideErrorState() {
        manager.startListening()
        assertEquals(VoiceState.LISTENING, manager.state.value)

        manager.clearError()

        // Must not interrupt a legitimate in-progress session just because
        // clearError() was called (defensively) while not in ERROR.
        assertEquals(VoiceState.LISTENING, manager.state.value)
    }

    @Test
    fun testAfterClearErrorTheUserCanStartListeningAgain() {
        manager.startListening()
        stt.emit(SpeechToTextEvent.Error("mic failure", recoverable = true))
        testDispatcher.scheduler.advanceUntilIdle()
        manager.clearError()

        manager.startListening()

        assertEquals(VoiceState.LISTENING, manager.state.value)
        assertTrue(stt.startListeningCalled)
    }

    @Test
    fun testFinalTranscriptTransitionsToProcessing() {
        manager.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.PROCESSING, manager.state.value)
    }

    @Test
    fun testSpeakTransitionsToSpeakingAndInvokesEngine() {
        manager.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("hello"))
        testDispatcher.scheduler.advanceUntilIdle()
        manager.speak("hi there")
        assertEquals(VoiceState.SPEAKING, manager.state.value)
        assertEquals("hi there", tts.lastSpokenText)
    }

    @Test
    fun testTtsCompletedReturnsToIdleAndAbandonsFocus() {
        manager.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("hello"))
        testDispatcher.scheduler.advanceUntilIdle()
        manager.speak("hi there")
        tts.emit(TextToSpeechEvent.Completed)
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.IDLE, manager.state.value)
        assertTrue(audio.abandonFocusCalled)
    }

    @Test
    fun testCancelResetsFromAnyStateIncludingError() {
        manager.startListening()
        stt.emit(SpeechToTextEvent.Error("mic failure", recoverable = true))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.ERROR, manager.state.value) // sanity check: this test must actually be starting from ERROR
        manager.cancel()
        assertEquals(VoiceState.IDLE, manager.state.value)
        assertTrue(stt.cancelCalled)
    }

    @Test
    fun testFocusLostMidListeningResetsToIdle() {
        manager.startListening()
        audio.simulateFocusLost()
        assertEquals(VoiceState.IDLE, manager.state.value)
        assertTrue(stt.cancelCalled)
    }
}
