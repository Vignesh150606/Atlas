package com.atlas.automation

import com.atlas.data.models.DeviceAction
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation.
 *
 * The Android-side half of the mission's tool-architecture diagram:
 *   Voice -> Intent -> Planner -> Tool Router -> Android Tool -> Result -> Memory
 * The backend's Planner + ToolRouter (app/planner/planner.py,
 * app/tools/router.py) produce the DeviceAction directive; this class is
 * where "Android Tool -> Result" happens - it maps that directive onto
 * exactly one of the six automation modules and returns an AutomationResult,
 * which ChatViewModel/ConversationAudioController then report back via
 * POST /chat/device-result to close the "-> Memory" step.
 *
 * `module`/`action`/`args` key names below are a hard contract with
 * app/tools/device_tools.py on the backend - see DEVICE_TOOL_NAMES there
 * for the authoritative list this must stay in sync with (also covered by
 * AutomationToolRouterTest so drift is caught in this repo, not only in
 * the backend's tests).
 */
interface AutomationToolRouter {
    suspend fun execute(action: DeviceAction): AutomationResult
}

@Singleton
class AutomationToolRouterImpl @Inject constructor(
    private val appManager: AppManager,
    private val accessibilityBridge: AccessibilityBridge,
    private val notificationBridge: NotificationBridge,
    private val mediaSessionController: MediaSessionControllerApi,
    private val clipboardTool: ClipboardTool,
    private val intentTool: IntentTool
) : AutomationToolRouter {

    override suspend fun execute(action: DeviceAction): AutomationResult {
        return try {
            when (action.module) {
                "app_manager" -> dispatchAppManager(action)
                "accessibility" -> dispatchAccessibility(action)
                "notifications" -> dispatchNotifications(action)
                "media_session" -> dispatchMedia(action)
                "clipboard" -> dispatchClipboard(action)
                "intent" -> dispatchIntent(action)
                else -> AutomationResult.failed("Unknown automation module '${action.module}'.")
            }
        } catch (e: Exception) {
            // Defensive backstop only - every module above already catches
            // the platform exceptions it knows how to expect (SecurityException,
            // ActivityNotFoundException, PackageManager.NameNotFoundException).
            // This exists so a truly unexpected failure still becomes a clean
            // AutomationResult instead of crashing the app mid-conversation.
            AutomationResult.failed("Something went wrong performing that action: ${e.message ?: e::class.simpleName}")
        }
    }

    private suspend fun dispatchAppManager(action: DeviceAction): AutomationResult = when (action.action) {
        "launch_app" -> appManager.launchApp(action.args["query"].orEmpty())
        "search_app" -> appManager.searchApps(action.args["query"].orEmpty())
        else -> unknownAction(action)
    }

    private suspend fun dispatchAccessibility(action: DeviceAction): AutomationResult = when (action.action) {
        "click" -> accessibilityBridge.click(action.args["target"].orEmpty())
        "long_click" -> accessibilityBridge.longClick(action.args["target"].orEmpty())
        "scroll" -> accessibilityBridge.scroll(action.args["direction"] ?: "down")
        "type_text" -> accessibilityBridge.typeText(action.args["target"].orEmpty(), action.args["text"].orEmpty())
        "back" -> accessibilityBridge.back()
        "home" -> accessibilityBridge.home()
        "recents" -> accessibilityBridge.recents()
        "open_notifications" -> accessibilityBridge.openNotifications()
        "read_screen" -> accessibilityBridge.readScreen()
        else -> unknownAction(action)
    }

    private suspend fun dispatchNotifications(action: DeviceAction): AutomationResult {
        val appFilter = action.args["app_filter"]
        // Phase 10: optional category routing (see NotificationCategorizer)
        // - backend passes a lowercase category name in args["category"]
        // when the Planner recognized one (e.g. "show me my important
        // notifications"); an unrecognized/absent value is treated as "no
        // filter" rather than an error, since this is a refinement, not a
        // required argument.
        val category = action.args["category"]?.let { raw ->
            runCatching { com.atlas.automation.NotificationCategory.valueOf(raw.trim().uppercase()) }.getOrNull()
        }
        return when (action.action) {
            "list" -> notificationBridge.list(appFilter, category)
            "summarize" -> notificationBridge.summarize(appFilter, category)
            "group" -> notificationBridge.group()
            else -> unknownAction(action)
        }
    }

    private suspend fun dispatchMedia(action: DeviceAction): AutomationResult = when (action.action) {
        "play" -> mediaSessionController.play()
        "pause" -> mediaSessionController.pause()
        "next" -> mediaSessionController.next()
        "previous" -> mediaSessionController.previous()
        "volume_up" -> mediaSessionController.volumeUp()
        "volume_down" -> mediaSessionController.volumeDown()
        "now_playing" -> mediaSessionController.nowPlaying()
        else -> unknownAction(action)
    }

    private suspend fun dispatchClipboard(action: DeviceAction): AutomationResult = when (action.action) {
        "read" -> clipboardTool.read()
        "write" -> clipboardTool.write(action.args["text"].orEmpty())
        else -> unknownAction(action)
    }

    private suspend fun dispatchIntent(action: DeviceAction): AutomationResult = when (action.action) {
        "open_url" -> intentTool.openUrl(action.args["url"].orEmpty())
        "dial" -> intentTool.dial(action.args["number"].orEmpty())
        "contacts" -> intentTool.openContacts()
        "share" -> intentTool.share(action.args["text"].orEmpty())
        "maps" -> intentTool.openMaps(action.args["query"].orEmpty())
        "email" -> intentTool.composeEmail(action.args["to"].orEmpty(), action.args["subject"], action.args["body"])
        else -> unknownAction(action)
    }

    private fun unknownAction(action: DeviceAction): AutomationResult =
        AutomationResult.failed("Unknown '${action.module}' action '${action.action}'.")
}
