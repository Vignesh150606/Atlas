package com.atlas

import com.atlas.api.HealthResponse
import com.atlas.automation.AutomationResult
import com.atlas.data.models.ChatResponse
import com.atlas.data.models.DeviceAction
import com.atlas.data.models.MessageStatus
import com.atlas.data.repository.ChatRepository
import com.atlas.ui.screens.chat.ChatViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class FakeChatRepository : ChatRepository {
    var shouldFail = false
    var deviceAction: DeviceAction? = null
    var reportedActions = mutableListOf<com.atlas.data.models.DeviceActionResultRequest>()

    override suspend fun checkHealth(): Result<HealthResponse> {
        return if (!shouldFail) {
            Result.success(HealthResponse(status = "healthy", version = "1.0", database = "connected"))
        } else {
            Result.failure(Exception("Connection refused"))
        }
    }

    override suspend fun sendMessage(message: String, conversationId: Int?): Result<ChatResponse> {
        return if (!shouldFail) {
            Result.success(
                ChatResponse(
                    response = "ATLAS received: $message",
                    conversationId = conversationId ?: 1,
                    deviceAction = deviceAction
                )
            )
        } else {
            Result.failure(Exception("Network error"))
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
// ConversationAudioControllerTest - see that file's doc comment for why.

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var fakeRepository: FakeChatRepository
    private lateinit var fakeAutomationToolRouter: FakeAutomationToolRouter
    private lateinit var viewModel: ChatViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        fakeRepository = FakeChatRepository()
        fakeAutomationToolRouter = FakeAutomationToolRouter()
        // Phase 8: ChatViewModel gained a required automationToolRouter
        // constructor param - this call was still 1-arg here and would not
        // have compiled. See ChatViewModel.executeDeviceAction().
        viewModel = ChatViewModel(fakeRepository, fakeAutomationToolRouter)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testBackendHealthCheckSuccess() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(viewModel.uiState.value.backendConnected)
    }

    @Test
    fun testSendMessageSuccess() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.onInputTextChanged("Hello ATLAS")
        viewModel.sendMessage()

        testDispatcher.scheduler.advanceUntilIdle()
        val state = viewModel.uiState.value
        assertEquals(2, state.messages.size)
        assertEquals("Hello ATLAS", state.messages[0].text)
        assertEquals("ATLAS received: Hello ATLAS", state.messages[1].text)
        assertFalse(state.isLoading)
    }

    @Test
    fun testSendMessageFailureMarksMessageFailed() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.shouldFail = true

        viewModel.onInputTextChanged("Hello ATLAS")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(1, state.messages.size)
        assertEquals(MessageStatus.FAILED, state.messages[0].status)
        assertFalse(state.isLoading)
        assertNotNull(state.error)
    }

    @Test
    fun testRetryMessageAfterFailureSucceeds() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.shouldFail = true

        viewModel.onInputTextChanged("Hello ATLAS")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        val failedMessageId = viewModel.uiState.value.messages[0].id
        fakeRepository.shouldFail = false
        viewModel.retryMessage(failedMessageId)
        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(2, state.messages.size)
        assertEquals(MessageStatus.SENT, state.messages[0].status)
        assertEquals("Hello ATLAS", state.messages[0].text)
        assertEquals("ATLAS received: Hello ATLAS", state.messages[1].text)
        assertFalse(state.isLoading)
        assertNull(state.error)
    }

    @Test
    fun testDeviceActionIsExecutedAndReportedAsAFollowUpMessage() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.deviceAction = DeviceAction(
            tool = "launch_app", module = "app_manager", action = "launch_app", args = mapOf("query" to "WhatsApp")
        )
        fakeAutomationToolRouter.result = AutomationResult.ok("Opened WhatsApp.")

        viewModel.onInputTextChanged("Open WhatsApp")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals("launch_app", fakeAutomationToolRouter.lastExecuted?.tool)

        val state = viewModel.uiState.value
        // user message, LLM's pre-action text, then the verified outcome
        assertEquals(3, state.messages.size)
        assertTrue(state.messages.last().text.contains("Opened WhatsApp."))

        assertEquals(1, fakeRepository.reportedActions.size)
        assertTrue(fakeRepository.reportedActions.first().success)
    }

    @Test
    fun testFailedDeviceActionShowsWarningPrefixNotCheckmark() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.deviceAction = DeviceAction(
            tool = "launch_app", module = "app_manager", action = "launch_app", args = mapOf("query" to "Nope")
        )
        fakeAutomationToolRouter.result = AutomationResult.failed("No app matching 'Nope' was found.")

        viewModel.onInputTextChanged("Open Nope")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        val lastMessage = viewModel.uiState.value.messages.last()
        assertTrue(lastMessage.text.contains("No app matching 'Nope' was found."))
        assertFalse(lastMessage.text.startsWith("\u2705"))
    }

    @Test
    fun testOrdinaryMessageWithNoDeviceActionDoesNotCallAutomationRouter() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.deviceAction = null

        viewModel.onInputTextChanged("What is the capital of France?")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(fakeAutomationToolRouter.lastExecuted)
        assertTrue(fakeRepository.reportedActions.isEmpty())
        assertEquals(2, viewModel.uiState.value.messages.size)
    }

    // --- Phase 10: confirmation gating (mission brief section 9) -----------
    @Test
    fun testConfirmationRequiredActionIsStagedNotExecuted() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )

        viewModel.onInputTextChanged("Call 5551234")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        // Not executed yet - just staged for confirmation.
        assertNull(fakeAutomationToolRouter.lastExecuted)
        assertNotNull(viewModel.uiState.value.pendingConfirmation)
        assertEquals("dial", viewModel.uiState.value.pendingConfirmation?.action)
    }

    @Test
    fun testConfirmingPendingActionExecutesItAndClearsPendingState() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )
        fakeAutomationToolRouter.result = AutomationResult.ok("Dialed 5551234.")

        viewModel.onInputTextChanged("Call 5551234")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        viewModel.confirmPendingDeviceAction()
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(viewModel.uiState.value.pendingConfirmation)
        assertEquals("dial", fakeAutomationToolRouter.lastExecuted?.action)
        assertTrue(viewModel.uiState.value.messages.last().text.contains("Dialed 5551234."))
    }

    @Test
    fun testCancellingPendingActionNeverExecutesItButReportsCancellation() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.deviceAction = DeviceAction(
            tool = "dial", module = "intent", action = "dial",
            args = mapOf("number" to "5551234"), requiresConfirmation = true
        )

        viewModel.onInputTextChanged("Call 5551234")
        viewModel.sendMessage()
        testDispatcher.scheduler.advanceUntilIdle()

        viewModel.cancelPendingDeviceAction()
        testDispatcher.scheduler.advanceUntilIdle()

        assertNull(viewModel.uiState.value.pendingConfirmation)
        assertNull(fakeAutomationToolRouter.lastExecuted)
        assertEquals(1, fakeRepository.reportedActions.size)
        assertFalse(fakeRepository.reportedActions.first().success)
        assertTrue(viewModel.uiState.value.messages.last().text.contains("won't do that"))
    }
}
