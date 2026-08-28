package com.atlas.automation

import android.accessibilityservice.AccessibilityService
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

/**
 * Phase 8: Android Automation Foundation - Accessibility Service module.
 *
 * Implements read UI hierarchy / locate controls / click / long click /
 * scroll / type text / back / home / recents / open notifications using
 * only the official android.accessibilityservice.AccessibilityService and
 * android.view.accessibility.AccessibilityNodeInfo APIs - no shell
 * commands, no reflection into private framework classes, no
 * instrumentation tricks.
 *
 * This class only implements the raw platform mechanics. Every design
 * decision about *when* to act on the user's behalf lives up in
 * AutomationToolRouter / the backend Planner - this class has no opinion
 * on that, matching the same separation VoiceManager keeps from
 * ConversationAudioController.
 */
@AndroidEntryPoint
class AtlasAccessibilityService : AccessibilityService() {

    @Inject
    lateinit var bridge: AccessibilityBridgeImpl

    override fun onServiceConnected() {
        super.onServiceConnected()
        bridge.attach(this)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            event.packageName?.toString()?.let { bridge.onForegroundPackageChanged(it) }
        }
    }

    override fun onInterrupt() {
        bridge.detach(this)
    }

    override fun onDestroy() {
        bridge.detach(this)
        super.onDestroy()
    }

    // --- Targeted actions --------------------------------------------------

    fun performClick(target: String): AutomationResult {
        val node = findNode(target) ?: return notFound(target)
        val clickable = nearestClickableAncestor(node) ?: return AutomationResult.failed(
            "Found '$target' on screen, but nothing near it responds to a tap."
        )
        return if (clickable.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            AutomationResult.ok("Tapped '$target'.")
        } else {
            AutomationResult.failed("Found '$target' but the tap didn't go through.")
        }
    }

    fun performLongClick(target: String): AutomationResult {
        val node = findNode(target) ?: return notFound(target)
        val clickable = nearestClickableAncestor(node) ?: return AutomationResult.failed(
            "Found '$target' on screen, but nothing near it responds to a long press."
        )
        return if (clickable.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)) {
            AutomationResult.ok("Long-pressed '$target'.")
        } else {
            AutomationResult.failed("Found '$target' but the long press didn't go through.")
        }
    }

    fun performScroll(direction: String): AutomationResult {
        val root = rootInActiveWindow ?: return noActiveWindow()
        val scrollable = findFirstScrollable(root)
            ?: return AutomationResult.failed("Nothing on this screen looks scrollable.")
        val action = if (direction == "up") {
            AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        } else {
            AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        }
        return if (scrollable.performAction(action)) {
            AutomationResult.ok("Scrolled $direction.")
        } else {
            AutomationResult.failed("Tried to scroll $direction but the screen didn't respond.")
        }
    }

    fun performTypeText(target: String, text: String): AutomationResult {
        val node = findNode(target) ?: return notFound(target)
        if (!node.isEditable) {
            return AutomationResult.failed("Found '$target' but it isn't a text field.")
        }
        node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) {
            AutomationResult.ok("Typed '$text' into '$target'.")
        } else {
            AutomationResult.failed("Found the '$target' field but couldn't type into it.")
        }
    }

    fun performReadScreen(): AutomationResult {
        val root = rootInActiveWindow ?: return noActiveWindow()
        val texts = LinkedHashSet<String>()
        collectText(root, texts, limit = 40)
        if (texts.isEmpty()) {
            return AutomationResult.ok("The current screen doesn't have any readable text on it.")
        }
        val summary = texts.joinToString(", ")
        return AutomationResult.ok("Screen shows: $summary", details = mapOf("item_count" to texts.size.toString()))
    }

    // --- Global (system-wide) actions --------------------------------------

    internal fun performGlobalAction(action: GlobalNavAction): AutomationResult {
        val globalAction = when (action) {
            GlobalNavAction.BACK -> GLOBAL_ACTION_BACK
            GlobalNavAction.HOME -> GLOBAL_ACTION_HOME
            GlobalNavAction.RECENTS -> GLOBAL_ACTION_RECENTS
            GlobalNavAction.NOTIFICATIONS -> GLOBAL_ACTION_NOTIFICATIONS
        }
        val summary = when (action) {
            GlobalNavAction.BACK -> "Pressed back."
            GlobalNavAction.HOME -> "Went to the home screen."
            GlobalNavAction.RECENTS -> "Opened recent apps."
            GlobalNavAction.NOTIFICATIONS -> "Opened the notification shade."
        }
        return if (performGlobalAction(globalAction)) {
            AutomationResult.ok(summary)
        } else {
            AutomationResult.failed("Couldn't complete that action.")
        }
    }

    // --- Node-tree search helpers -------------------------------------------

    /** Case-insensitive search over text/content-description across the
     * active window's node tree - the "locate controls" capability. */
    private fun findNode(target: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        val needle = target.trim().lowercase()
        if (needle.isEmpty()) return null
        return findNodeRecursive(root, needle)
    }

    private fun findNodeRecursive(node: AccessibilityNodeInfo, needle: String): AccessibilityNodeInfo? {
        val text = node.text?.toString()?.lowercase()
        val desc = node.contentDescription?.toString()?.lowercase()
        if ((text != null && text.contains(needle)) || (desc != null && desc.contains(needle))) {
            return node
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val match = findNodeRecursive(child, needle)
            if (match != null) return match
        }
        return null
    }

    /** Many text/icon nodes aren't themselves clickable - the tappable
     * target is usually a clickable ancestor (a Button/Row wrapping the
     * label). Walks up until it finds one, or gives up at the root. */
    private fun nearestClickableAncestor(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var current: AccessibilityNodeInfo? = node
        while (current != null) {
            if (current.isClickable) return current
            current = current.parent
        }
        return null
    }

    private fun findFirstScrollable(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (node.isScrollable) return node
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val match = findFirstScrollable(child)
            if (match != null) return match
        }
        return null
    }

    private fun collectText(node: AccessibilityNodeInfo, out: MutableSet<String>, limit: Int) {
        if (out.size >= limit) return
        node.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }?.let { out.add(it) }
        for (i in 0 until node.childCount) {
            if (out.size >= limit) return
            val child = node.getChild(i) ?: continue
            collectText(child, out, limit)
        }
    }

    private fun notFound(target: String) =
        AutomationResult.failed("Couldn't find anything matching '$target' on the current screen.")

    private fun noActiveWindow() =
        AutomationResult.failed("Couldn't read the current screen - no active window.")
}
