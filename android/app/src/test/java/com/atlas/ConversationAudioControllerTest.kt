package com.atlas

import com.atlas.api.HealthResponse
import com.atlas.automation.AutomationResult
import com.atlas.data.models.ChatResponse
import com.atlas.data.models.DeviceAction
import com.atlas.data.repository.ChatRepository
import com.atlas.voice.ConversationAudioController
import com.atlas.voice.SpeechToTextEvent
import com.atlas.voice.VoiceManager
import com.atlas.voice.VoiceState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.test.advanceUntilIdle
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

private class FakeChatRepositoryForVoice : ChatRepository {
    var shouldFail = false
    var failureMessage = "Couldn't reach ATLAS."
    var responseText = "Hello from ATLAS"
    var deviceAction: DeviceAction? = null
    var reportedActions = mutableListOf<com.atlas.data.models.DeviceActionResultRequest>()

    override suspend fun checkHealth(): Result<HealthResponse> =
        Result.success(HealthResponse(status = "healthy", version = "1.0", database = "connected"))

    override suspend fun sendMessage(message: String, conversationId: Int?): Result<ChatResponse> {
        return if (shouldFail) {
            Result.failure(Exception(failureMessage))
        } else {
            Result.success(
                ChatResponse(response = responseText, conversationId = conversationId ?: 1, deviceAction = deviceAction)
            )
        }
    }

    // Phase 8: Android Automation Foundation
    override suspend fun reportDeviceAction(
        request: com.atlas.data.models.DeviceActionResultRequest
    ): Result<com.atlas.data.models.DeviceActionResultResponse> {
        reportedActions.add(request)
        return Result.success(
            com.atlas.data.models.DeviceActionResultResponse(
                id = 1, role = "assistant", content = request.summary
            )
        )
    }
}

// FakeAutomationToolRouter now lives in AutomationFakes.kt, shared with
// ChatViewModelTest - see that file's doc comment for why. Its default
// `result` moved from "Opened WhatsApp." to the generic "Done."; every
// test below that cares about the result sets it explicitly (e.g.
// testDeviceActionSpeaksTheAutomationResultNotTheRawLlmText), so this is
// not a behavior change for any test in this file.

/**
 * Phase 8 stabilization. Covers the exact user-visible bug: tapping "Retry"
 * on the Voice screen called clearError(), which cleared the error text but
 * left VoiceSessionState.voiceState stuck at ERROR, so the orb never
 * recovered. testRetryAfterErrorReturnsSessionToIdle is the direct
 * regression test for that; everything else here is baseline coverage that
 * didn't exist for this class before (see VoiceEngineFakes.kt for why it
 * couldn't exist before the AudioSessionManager interface extraction).
 *
 * testDeviceAction* cases cover the other Phase 8 gap this class had: an
 * injected-but-never-called AutomationToolRouter meant a
 * ChatResponse.device_action was silently dropped in voice mode.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ConversationAudioControllerTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var stt: FakeSpeechToTextEngine
    private lateinit var tts: FakeTextToSpeechEngine
    private lateinit var audio: FakeAudioSessionManager
    private lateinit var voiceManager: VoiceManager
    private lateinit var chatRepository: FakeChatRepositoryForVoice
    private lateinit var automationToolRouter: FakeAutomationToolRouter
    private lateinit var controller: ConversationAudioController

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        stt = FakeSpeechToTextEngine()
        tts = FakeTextToSpeechEngine()
        audio = FakeAudioSessionManager()
        voiceManager = VoiceManager(stt, tts, audio)
        chatRepository = FakeChatRepositoryForVoice()
        automationToolRouter = FakeAutomationToolRouter()
        controller = ConversationAudioController(voiceManager, chatRepository, automationToolRouter)
        // Both VoiceManager.init{} and ConversationAudioController.init{}
        // launch flow collectors on Dispatchers.Main.immediate, backed here
        // by StandardTestDispatcher - those launches are only *scheduled*
        // until the scheduler is pumped. Without this, the collectors
        // haven't subscribed yet by the time a test calls stt.emit(), and
        // since the underlying SharedFlows default to replay = 0, an emit
        // with nobody subscribed is dropped permanently - a later
        // advanceUntilIdle() call does not retroactively deliver it. This
        // one-time pump lets every collector subscribe first.
        testDispatcher.scheduler.advanceUntilIdle()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testRetryAfterErrorReturnsSessionToIdle() {
        controller.startListening()
        stt.emit(SpeechToTextEvent.Error("mic failure", recoverable = true))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.ERROR, controller.sessionState.value.voiceState)
        assertNotNull(controller.sessionState.value.error)

        controller.clearError()
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(
            "Retry (clearError()) must bring the session's voiceState back to IDLE, not just clear the error text - this is the Phase 8 stabilization fix",
            VoiceState.IDLE,
            controller.sessionState.value.voiceState
        )
        assertNull(controller.sessionState.value.error)
    }

    @Test
    fun testAfterRetryTheUserCanStartListeningAgain() {
        controller.startListening()
        stt.emit(SpeechToTextEvent.Error("mic failure", recoverable = true))
        testDispatcher.scheduler.advanceUntilIdle()
        controller.clearError()

        controller.startListening()
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(VoiceState.LISTENING, controller.sessionState.value.voiceState)
    }

    @Test
    fun testFailedChatDispatchPutsSessionIntoErrorWithMessage() {
        chatRepository.shouldFail = true
        chatRepository.failureMessage = "Network error"

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(VoiceState.ERROR, controller.sessionState.value.voiceState)
        assertEquals("Network error", controller.sessionState.value.error)
    }

    @Test
    fun testFailedChatDispatchCanBeRecoveredWithClearError() {
        chatRepository.shouldFail = true
        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.ERROR, controller.sessionState.value.voiceState)

        controller.clearError()
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(VoiceState.IDLE, controller.sessionState.value.voiceState)
    }

    @Test
    fun testSuccessfulChatDispatchSpeaksTheResponse() {
        chatRepository.responseText = "Opening WhatsApp now."
        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals("Opening WhatsApp now.", tts.lastSpokenText)
        assertEquals(VoiceState.SPEAKING, controller.sessionState.value.voiceState)
    }

    @Test
    fun testCancelClearsTranscriptAndError() {
        controller.startListening()
        stt.emit(SpeechToTextEvent.Error("mic failure", recoverable = true))
        testDispatcher.scheduler.advanceUntilIdle()
        assertNotNull(controller.sessionState.value.error) // sanity check: there must be a real error here to clear

        controller.cancel()
        testDispatcher.scheduler.advanceUntilIdle() // voiceState is only ever written by the voiceManager.state collector (see cancel()'s doc/clearError() precedent) - the direct fields (error/transcript) don't need this, but voiceState does.

        assertEquals(VoiceState.IDLE, controller.sessionState.value.voiceState)
        assertNull(controller.sessionState.value.error)
        assertEquals("", controller.sessionState.value.transcript)
    }

    @Test
    fun testStartListeningRefreshesOutputRoute() {
        audio.outputRoute = com.atlas.voice.AudioOutputRoute.BLUETOOTH
        controller.startListening()
        assertEquals(com.atlas.voice.AudioOutputRoute.BLUETOOTH, controller.sessionState.value.outputRoute)
    }

    @Test
    fun testContinuousModeAutoResumesListeningAfterSpeaking() {
        controller.setContinuousMode(true)
        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.SPEAKING, controller.sessionState.value.voiceState)

        tts.emit(com.atlas.voice.TextToSpeechEvent.Completed)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(
            "continuous mode should auto-resume listening once ATLAS finishes speaking",
            VoiceState.LISTENING,
            controller.sessionState.value.voiceState
        )
    }

    @Test
    fun testPushToTalkDoesNotAutoResumeListeningAfterSpeaking() {
        controller.setContinuousMode(false)
        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()

        tts.emit(com.atlas.voice.TextToSpeechEvent.Completed)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(VoiceState.IDLE, controller.sessionState.value.voiceState)
    }

    @Test
    fun testDeviceActionIsExecutedViaAutomationToolRouter() {
        chatRepository.deviceAction = DeviceAction(
            tool = "launch_app", module = "app_manager", action = "launch_app", args = mapOf("query" to "WhatsApp")
        )
        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals("launch_app", automationToolRouter.lastExecuted?.tool)
        assertEquals(mapOf("query" to "WhatsApp"), automationToolRouter.lastExecuted?.args)
    }

    @Test
    fun testDeviceActionSpeaksTheAutomationResultNotTheRawLlmText() {
        chatRepository.responseText = "Sure, opening WhatsApp now."
        chatRepository.deviceAction = DeviceAction(
            tool = "launch_app", module = "app_manager", action = "launch_app", args = mapOf("query" to "WhatsApp")
        )
        automationToolRouter.result = AutomationResult.ok("Opened WhatsApp.")

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open whatsapp"))
        testDispatcher.scheduler.advanceUntilIdle()

        // Must speak the *verified* outcome, not the LLM's pre-action text -
        // see the doc comment on ConversationAudioController.handleDeviceAction.
        assertEquals("Opened WhatsApp.", tts.lastSpokenText)
    }

    @Test
    fun testFailedDeviceActionStillSpeaksAResult() {
        chatRepository.deviceAction = DeviceAction(
            tool = "launch_app", module = "app_manager", action = "launch_app", args = mapOf("query" to "Nonexistent")
        )
        automationToolRouter.result = AutomationResult.failed("No app matching 'Nonexistent' was found.")

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("open nonexistent"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals("No app matching 'Nonexistent' was found.", tts.lastSpokenText)
    }

    @Test
    fun testDeviceActionResultIsReportedBackToBackend() {
        chatRepository.deviceAction = DeviceAction(
            tool = "media", module = "media_session", action = "pause", args = emptyMap()
        )
        automationToolRouter.result = AutomationResult.ok("Paused.")

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("pause"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, chatRepository.reportedActions.size)
        val reported = chatRepository.reportedActions.first()
        assertEquals("media", reported.tool)
        assertEquals("pause", reported.action)
        assertTrue(reported.success)
        assertEquals("Paused.", reported.summary)
    }

    @Test
    fun testOrdinaryResponseWithNoDeviceActionIsUnaffected() {
        chatRepository.deviceAction = null
        chatRepository.responseText = "The capital of France is Paris."

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("what is the capital of France"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals("The capital of France is Paris.", tts.lastSpokenText)
        assertNull(automationToolRouter.lastExecuted)
        assertTrue(chatRepository.reportedActions.isEmpty())
    }

    // --- Phase 10: confirmation gating (mission brief section 9) - "Never
    // bypass confirmation merely because the user is using voice" -----------
    @Test
    fun testConfirmationRequiredActionIsStagedNotExecuted() {
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(automationToolRouter.lastExecuted)
        assertNotNull(controller.sessionState.value.pendingConfirmation)
        assertEquals("dial", controller.sessionState.value.pendingConfirmation?.action)
        assertTrue(chatRepository.reportedActions.isEmpty())
    }

    @Test
    fun testConfirmingPendingActionExecutesItAndClearsPendingState() {
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )
        automationToolRouter.result = AutomationResult.ok("Dialed 5551234.")

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()

        controller.confirmPendingDeviceAction()
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(controller.sessionState.value.pendingConfirmation)
        assertEquals("dial", automationToolRouter.lastExecuted?.action)
        assertEquals("Dialed 5551234.", tts.lastSpokenText)
    }

    @Test
    fun testCancellingPendingActionNeverExecutesItButReportsCancellation() {
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()

        controller.cancelPendingDeviceAction()
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(controller.sessionState.value.pendingConfirmation)
        assertNull(automationToolRouter.lastExecuted)
        assertEquals(1, chatRepository.reportedActions.size)
        assertFalse(chatRepository.reportedActions.first().success)
    }

    @Test
    fun testSecondUtteranceWhilePendingConfirmationDoesNotOverwriteIt() {
        // Regression test: continuous mode (or the user simply speaking
        // again) can produce a second final transcript before the first
        // confirmation is resolved - VoiceManager forwards FinalResult
        // unconditionally regardless of state (see handleSttEvent), so
        // nothing upstream blocks this. Without a guard, that second
        // utterance would dispatch as an ordinary chat message and, if it
        // also produced a device action, silently overwrite
        // pendingConfirmation - orphaning the first, still on-screen
        // confirmation with no way back to it.
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )
        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals("dial", controller.sessionState.value.pendingConfirmation?.action)

        chatRepository.deviceAction = DeviceAction(
            tool = "clipboard", module = "clipboard", action = "write",
            args = mapOf("text" to "something else"), requiresConfirmation = true
        )
        stt.emit(SpeechToTextEvent.FinalResult("copy something else to clipboard"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(
            "a second utterance while a confirmation is pending must not overwrite it",
            "dial",
            controller.sessionState.value.pendingConfirmation?.action
        )
        // Nothing was executed or reported for the second (blocked) utterance.
        assertNull(automationToolRouter.lastExecuted)
        assertTrue(chatRepository.reportedActions.isEmpty())
    }

    // --- Phase 11 section 5: voice-native confirmation ---------------------
    @Test
    fun testSayingYesConfirmsPendingActionByVoice() {
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )
        automationToolRouter.result = AutomationResult.ok("Dialed 5551234.")
        controller.setContinuousMode(true)

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()
        assertNotNull(controller.sessionState.value.pendingConfirmation)

        // ATLAS finishes speaking the confirmation heads-up - continuous
        // mode auto-resumes listening for the answer (see
        // handleStateTransition's AWAITING_CONFIRMATION branch).
        tts.emit(com.atlas.voice.TextToSpeechEvent.Completed)
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(VoiceState.LISTENING, controller.sessionState.value.voiceState)

        stt.emit(SpeechToTextEvent.FinalResult("yes"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(controller.sessionState.value.pendingConfirmation)
        assertEquals("dial", automationToolRouter.lastExecuted?.action)
        assertEquals("Dialed 5551234.", tts.lastSpokenText)
    }

    @Test
    fun testSayingNoCancelsPendingActionByVoice() {
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )
        controller.setContinuousMode(true)

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()

        tts.emit(com.atlas.voice.TextToSpeechEvent.Completed)
        testDispatcher.scheduler.advanceUntilIdle()

        stt.emit(SpeechToTextEvent.FinalResult("no"))
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(controller.sessionState.value.pendingConfirmation)
        assertNull(automationToolRouter.lastExecuted)
        assertEquals(1, chatRepository.reportedActions.size)
        assertFalse(chatRepository.reportedActions.first().success)
    }

    @Test
    fun testUnclearAnswerReEntersAwaitingConfirmationAndDoesNotResolveEitherWay() {
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )
        controller.setContinuousMode(true)

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()

        tts.emit(com.atlas.voice.TextToSpeechEvent.Completed)
        testDispatcher.scheduler.advanceUntilIdle()

        stt.emit(SpeechToTextEvent.FinalResult("what time is it"))
        testDispatcher.scheduler.advanceUntilIdle()

        // Still pending - an unclear answer must not resolve it either way.
        assertNotNull(controller.sessionState.value.pendingConfirmation)
        assertNull(automationToolRouter.lastExecuted)
        assertEquals("Sorry, was that a yes or a no? You can also check your screen.", tts.lastSpokenText)
    }

    @Test
    fun testPushToTalkDoesNotAutoListenForConfirmationAnswer() {
        // "Nothing listens without being asked" holds for the
        // confirmation answer too - push-to-talk still requires an
        // explicit tap (now wired in VoiceScreen's handleOrbTap), even
        // right after being asked a direct yes/no question.
        chatRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )
        controller.setContinuousMode(false)

        controller.startListening()
        stt.emit(SpeechToTextEvent.FinalResult("call 5551234"))
        testDispatcher.scheduler.advanceUntilIdle()

        tts.emit(com.atlas.voice.TextToSpeechEvent.Completed)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(VoiceState.AWAITING_CONFIRMATION, controller.sessionState.value.voiceState)
    }
}
