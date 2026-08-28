package com.atlas

import com.atlas.automation.AutomationResult
import com.atlas.automation.AutomationToolRouter
import com.atlas.data.models.DeviceAction

/**
 * Phase 8: Android Automation Foundation - shared test double for the
 * device-side dispatcher.
 *
 * ChatViewModelTest (text mode) and ConversationAudioControllerTest (voice
 * mode) both exercise the same ChatResponse.device_action ->
 * AutomationToolRouter.execute() contract (see
 * Phase8_ArchitectureUpdate.md §5 - "Wiring into the existing chat/voice
 * pipeline"), so they share one fake here instead of each file declaring
 * its own identical implementation. Matches the precedent already set by
 * VoiceEngineFakes.kt for FakeSpeechToTextEngine/FakeTextToSpeechEngine/
 * FakeAudioSessionManager, which the same two test areas also share.
 *
 * The default `result` is intentionally generic ("Done.") rather than
 * scenario-specific (e.g. "Opened WhatsApp.") precisely because it's now
 * shared - every test that cares about the returned AutomationResult
 * already sets `result` explicitly before triggering the action; no test
 * in either suite asserts on this default.
 */
class FakeAutomationToolRouter : AutomationToolRouter {
    var result: AutomationResult = AutomationResult.ok("Done.")
    var lastExecuted: DeviceAction? = null

    override suspend fun execute(action: DeviceAction): AutomationResult {
        lastExecuted = action
        return result
    }
}
