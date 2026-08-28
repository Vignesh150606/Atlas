package com.atlas

import com.atlas.automation.AccessibilityBridge
import com.atlas.automation.AppManager
import com.atlas.automation.AutomationResult
import com.atlas.automation.AutomationToolRouterImpl
import com.atlas.automation.ClipboardTool
import com.atlas.automation.IntentTool
import com.atlas.automation.MediaSessionControllerApi
import com.atlas.automation.NotificationBridge
import com.atlas.data.models.DeviceAction
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

private class FakeAppManager : AppManager {
    var lastLaunchQuery: String? = null
    var lastSearchQuery: String? = null
    override suspend fun launchApp(query: String): AutomationResult {
        lastLaunchQuery = query
        return AutomationResult.ok("Opened $query.")
    }
    override suspend fun searchApps(query: String): AutomationResult {
        lastSearchQuery = query
        return AutomationResult.ok("Found apps matching $query.")
    }
    override fun foregroundApp(): String? = null
}

private class FakeAccessibilityBridge : AccessibilityBridge {
    override val isConnected: StateFlow<Boolean> = MutableStateFlow(true)
    override val foregroundPackage: StateFlow<String?> = MutableStateFlow(null)
    var lastCall: String? = null

    override suspend fun click(target: String): AutomationResult { lastCall = "click:$target"; return AutomationResult.ok("Tapped $target.") }
    override suspend fun longClick(target: String): AutomationResult { lastCall = "long_click:$target"; return AutomationResult.ok("Long-pressed $target.") }
    override suspend fun scroll(direction: String): AutomationResult { lastCall = "scroll:$direction"; return AutomationResult.ok("Scrolled $direction.") }
    override suspend fun typeText(target: String, text: String): AutomationResult { lastCall = "type_text:$target:$text"; return AutomationResult.ok("Typed.") }
    override suspend fun back(): AutomationResult { lastCall = "back"; return AutomationResult.ok("Back.") }
    override suspend fun home(): AutomationResult { lastCall = "home"; return AutomationResult.ok("Home.") }
    override suspend fun recents(): AutomationResult { lastCall = "recents"; return AutomationResult.ok("Recents.") }
    override suspend fun openNotifications(): AutomationResult { lastCall = "open_notifications"; return AutomationResult.ok("Shade opened.") }
    override suspend fun readScreen(): AutomationResult { lastCall = "read_screen"; return AutomationResult.ok("Screen shows: nothing.") }
}

private class FakeNotificationBridge : NotificationBridge {
    override val isConnected: StateFlow<Boolean> = MutableStateFlow(true)
    var lastCall: String? = null

    override suspend fun list(appFilter: String?, category: com.atlas.automation.NotificationCategory?): AutomationResult { lastCall = "list:$appFilter:$category"; return AutomationResult.ok("Listed.") }
    override suspend fun summarize(appFilter: String?, category: com.atlas.automation.NotificationCategory?): AutomationResult { lastCall = "summarize:$appFilter:$category"; return AutomationResult.ok("Summarized.") }
    override suspend fun group(): AutomationResult { lastCall = "group"; return AutomationResult.ok("Grouped.") }
}

private class FakeMediaSessionController : MediaSessionControllerApi {
    var lastCall: String? = null
    override suspend fun play(): AutomationResult { lastCall = "play"; return AutomationResult.ok("Resuming.") }
    override suspend fun pause(): AutomationResult { lastCall = "pause"; return AutomationResult.ok("Paused.") }
    override suspend fun next(): AutomationResult { lastCall = "next"; return AutomationResult.ok("Next.") }
    override suspend fun previous(): AutomationResult { lastCall = "previous"; return AutomationResult.ok("Previous.") }
    override suspend fun volumeUp(): AutomationResult { lastCall = "volume_up"; return AutomationResult.ok("Louder.") }
    override suspend fun volumeDown(): AutomationResult { lastCall = "volume_down"; return AutomationResult.ok("Quieter.") }
    override suspend fun nowPlaying(): AutomationResult { lastCall = "now_playing"; return AutomationResult.ok("Nothing playing.") }
}

private class FakeClipboardTool : ClipboardTool {
    var lastCall: String? = null
    override suspend fun read(): AutomationResult { lastCall = "read"; return AutomationResult.ok("Clipboard: hi.") }
    override suspend fun write(text: String): AutomationResult { lastCall = "write:$text"; return AutomationResult.ok("Copied.") }
}

private class FakeIntentTool : IntentTool {
    var lastCall: String? = null
    override suspend fun openUrl(url: String): AutomationResult { lastCall = "open_url:$url"; return AutomationResult.ok("Opened $url.") }
    override suspend fun dial(number: String): AutomationResult { lastCall = "dial:$number"; return AutomationResult.ok("Dialing.") }
    override suspend fun openContacts(): AutomationResult { lastCall = "contacts"; return AutomationResult.ok("Contacts opened.") }
    override suspend fun share(text: String): AutomationResult { lastCall = "share:$text"; return AutomationResult.ok("Shared.") }
    override suspend fun openMaps(query: String): AutomationResult { lastCall = "maps:$query"; return AutomationResult.ok("Maps opened.") }
    override suspend fun composeEmail(to: String, subject: String?, body: String?): AutomationResult { lastCall = "email:$to:$subject:$body"; return AutomationResult.ok("Composing.") }
}

/**
 * Covers AutomationToolRouterImpl's module/action dispatch table - the
 * Android-side half of the hard contract with app/tools/device_tools.py's
 * DEVICE_TOOL_NAMES on the backend (see that router's class doc comment).
 * Each of these module/action string pairs must be spelled identically on
 * both sides; a typo on either end silently turns into "Unknown module/
 * action" at runtime instead of a compile error, which is exactly why this
 * suite enumerates every one explicitly rather than spot-checking a few.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class AutomationToolRouterTest {

    private lateinit var appManager: FakeAppManager
    private lateinit var accessibilityBridge: FakeAccessibilityBridge
    private lateinit var notificationBridge: FakeNotificationBridge
    private lateinit var mediaSessionController: FakeMediaSessionController
    private lateinit var clipboardTool: FakeClipboardTool
    private lateinit var intentTool: FakeIntentTool
    private lateinit var router: AutomationToolRouterImpl

    @Before
    fun setUp() {
        appManager = FakeAppManager()
        accessibilityBridge = FakeAccessibilityBridge()
        notificationBridge = FakeNotificationBridge()
        mediaSessionController = FakeMediaSessionController()
        clipboardTool = FakeClipboardTool()
        intentTool = FakeIntentTool()
        router = AutomationToolRouterImpl(
            appManager, accessibilityBridge, notificationBridge, mediaSessionController, clipboardTool, intentTool
        )
    }

    @Test
    fun testLaunchAppRoutesToAppManager() = runTest {
        val result = router.execute(DeviceAction("launch_app", "app_manager", "launch_app", mapOf("query" to "WhatsApp")))
        assertTrue(result.success)
        assertEquals("WhatsApp", appManager.lastLaunchQuery)
    }

    @Test
    fun testSearchAppRoutesToAppManager() = runTest {
        router.execute(DeviceAction("search_app", "app_manager", "search_app", mapOf("query" to "calc")))
        assertEquals("calc", appManager.lastSearchQuery)
    }

    @Test
    fun testAccessibilityClickRoutesWithTarget() = runTest {
        router.execute(DeviceAction("accessibility", "accessibility", "click", mapOf("target" to "Send")))
        assertEquals("click:Send", accessibilityBridge.lastCall)
    }

    @Test
    fun testAccessibilityTypeTextRoutesWithTargetAndText() = runTest {
        router.execute(DeviceAction("accessibility", "accessibility", "type_text", mapOf("target" to "Search", "text" to "pizza")))
        assertEquals("type_text:Search:pizza", accessibilityBridge.lastCall)
    }

    @Test
    fun testAccessibilityScrollDefaultsDirectionWhenMissing() = runTest {
        router.execute(DeviceAction("accessibility", "accessibility", "scroll", emptyMap()))
        assertEquals("scroll:down", accessibilityBridge.lastCall)
    }

    @Test
    fun testAccessibilityGlobalActionsAllRoute() = runTest {
        for (action in listOf("back", "home", "recents", "open_notifications", "read_screen")) {
            router.execute(DeviceAction("accessibility", "accessibility", action, emptyMap()))
            assertEquals(action, accessibilityBridge.lastCall)
        }
    }

    @Test
    fun testNotificationsSummarizeRoutesWithAppFilter() = runTest {
        router.execute(DeviceAction("notifications", "notifications", "summarize", mapOf("app_filter" to "Slack")))
        // Phase 10: FakeNotificationBridge.lastCall now also records the
        // (absent, here) category argument - see testNotificationsSummarizeRoutesWithCategory.
        assertEquals("summarize:Slack:null", notificationBridge.lastCall)
    }

    @Test
    fun testNotificationsGroupRoutes() = runTest {
        router.execute(DeviceAction("notifications", "notifications", "group", emptyMap()))
        assertEquals("group", notificationBridge.lastCall)
    }

    // --- Phase 10: category routing (mission brief section 10) -------------
    @Test
    fun testNotificationsSummarizeRoutesWithCategory() = runTest {
        router.execute(DeviceAction("notifications", "notifications", "summarize", mapOf("category" to "important")))
        assertEquals("summarize:null:IMPORTANT", notificationBridge.lastCall)
    }

    @Test
    fun testNotificationsListRoutesWithAppFilterAndCategory() = runTest {
        router.execute(DeviceAction(
            "notifications", "notifications", "list",
            mapOf("app_filter" to "Slack", "category" to "personal")
        ))
        assertEquals("list:Slack:PERSONAL", notificationBridge.lastCall)
    }

    @Test
    fun testNotificationsUnrecognizedCategoryIsTreatedAsNoFilter() = runTest {
        router.execute(DeviceAction("notifications", "notifications", "list", mapOf("category" to "not_a_real_category")))
        assertEquals("list:null:null", notificationBridge.lastCall)
    }

    @Test
    fun testAllMediaActionsRoute() = runTest {
        for (action in listOf("play", "pause", "next", "previous", "volume_up", "volume_down", "now_playing")) {
            router.execute(DeviceAction("media", "media_session", action, emptyMap()))
            assertEquals(action, mediaSessionController.lastCall)
        }
    }

    @Test
    fun testClipboardWriteRoutesWithText() = runTest {
        router.execute(DeviceAction("clipboard", "clipboard", "write", mapOf("text" to "hello")))
        assertEquals("write:hello", clipboardTool.lastCall)
    }

    @Test
    fun testClipboardReadRoutes() = runTest {
        router.execute(DeviceAction("clipboard", "clipboard", "read", emptyMap()))
        assertEquals("read", clipboardTool.lastCall)
    }

    @Test
    fun testIntentOpenUrlRoutes() = runTest {
        router.execute(DeviceAction("intent_action", "intent", "open_url", mapOf("url" to "https://example.com")))
        assertEquals("open_url:https://example.com", intentTool.lastCall)
    }

    @Test
    fun testIntentDialRoutes() = runTest {
        router.execute(DeviceAction("intent_action", "intent", "dial", mapOf("number" to "555-1234")))
        assertEquals("dial:555-1234", intentTool.lastCall)
    }

    @Test
    fun testIntentContactsRoutesWithNoArgs() = runTest {
        router.execute(DeviceAction("intent_action", "intent", "contacts", emptyMap()))
        assertEquals("contacts", intentTool.lastCall)
    }

    @Test
    fun testIntentMapsRoutesWithQuery() = runTest {
        router.execute(DeviceAction("intent_action", "intent", "maps", mapOf("query" to "Golden Gate Bridge")))
        assertEquals("maps:Golden Gate Bridge", intentTool.lastCall)
    }

    @Test
    fun testIntentEmailRoutesWithAllFields() = runTest {
        router.execute(DeviceAction("intent_action", "intent", "email", mapOf("to" to "a@b.com", "subject" to "Hi", "body" to "Hello")))
        assertEquals("email:a@b.com:Hi:Hello", intentTool.lastCall)
    }

    @Test
    fun testUnknownModuleFailsCleanly() = runTest {
        val result = router.execute(DeviceAction("x", "not_a_real_module", "do_something", emptyMap()))
        assertFalse(result.success)
        assertTrue(result.summary.contains("Unknown automation module"))
    }

    @Test
    fun testUnknownActionWithinKnownModuleFailsCleanly() = runTest {
        val result = router.execute(DeviceAction("media", "media_session", "shuffle", emptyMap()))
        assertFalse(result.success)
        assertTrue(result.summary.contains("Unknown"))
    }

    @Test
    fun testMissingArgsDefaultToEmptyStringRatherThanCrashing() = runTest {
        // No "target" key at all for click - AutomationToolRouterImpl uses
        // args["target"].orEmpty(), so this must not throw.
        val result = router.execute(DeviceAction("accessibility", "accessibility", "click", emptyMap()))
        assertTrue(result.success) // the fake always succeeds; the point is no exception was thrown
        assertEquals("click:", accessibilityBridge.lastCall)
    }
}
