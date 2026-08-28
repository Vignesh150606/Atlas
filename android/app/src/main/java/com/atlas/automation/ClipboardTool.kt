package com.atlas.automation

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation - Clipboard module.
 *
 * Implements read / write using only the official
 * android.content.ClipboardManager API.
 *
 * Since Android 10 (API 29), only the default input method or the app
 * currently in the foreground can read clipboard *content* (background
 * apps still see that a clip exists, just not its data) - a platform
 * privacy restriction, not something this class can work around, and it
 * isn't supposed to: an automation service silently reading the clipboard
 * from the background is exactly the kind of thing that restriction
 * exists to prevent. In practice this means read() reliably returns data
 * when ATLAS is the foreground app (e.g. right after a voice command) and
 * may return null otherwise - see docs/Phase8_KnownLimitations.md. Writing
 * has no such restriction.
 */
interface ClipboardTool {
    suspend fun read(): AutomationResult
    suspend fun write(text: String): AutomationResult
}

@Singleton
class AndroidClipboardTool @Inject constructor(
    @ApplicationContext private val context: Context
) : ClipboardTool {

    private val clipboardManager: ClipboardManager by lazy {
        context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    }

    override suspend fun read(): AutomationResult {
        if (!clipboardManager.hasPrimaryClip()) {
            return AutomationResult.ok("The clipboard is empty.")
        }
        val clip = clipboardManager.primaryClip
        val text = clip?.takeIf { it.itemCount > 0 }
            ?.getItemAt(0)
            ?.coerceToText(context)
            ?.toString()

        return if (text.isNullOrEmpty()) {
            AutomationResult.ok(
                "There's something on the clipboard, but ATLAS can't read its contents right now " +
                    "(Android only allows the app currently on screen to read clipboard data)."
            )
        } else {
            AutomationResult.ok("Clipboard contains: $text", details = mapOf("text" to text))
        }
    }

    override suspend fun write(text: String): AutomationResult {
        val clip = ClipData.newPlainText("ATLAS", text)
        clipboardManager.setPrimaryClip(clip)
        return AutomationResult.ok("Copied to clipboard.")
    }
}
