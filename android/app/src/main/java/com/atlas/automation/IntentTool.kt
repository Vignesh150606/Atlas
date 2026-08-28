package com.atlas.automation

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation - Intent module.
 *
 * Implements open URL / dial / open contacts / share / open maps / compose
 * email using only standard, documented implicit Intent actions
 * (ACTION_VIEW, ACTION_DIAL, ACTION_SEND, ACTION_SENDTO) - the same
 * mechanism any Android app uses to hand a task off to whichever app the
 * user has chosen to handle it (browser, dialer, maps app, mail app).
 * ACTION_DIAL (not ACTION_CALL) is used deliberately: it opens the dialer
 * pre-filled with the number and requires the user to press call
 * themselves, so no CALL_PHONE permission is needed and a voice
 * misrecognition can never place a call the user didn't confirm.
 */
interface IntentTool {
    suspend fun openUrl(url: String): AutomationResult
    suspend fun dial(number: String): AutomationResult
    suspend fun openContacts(): AutomationResult
    suspend fun share(text: String): AutomationResult
    suspend fun openMaps(query: String): AutomationResult
    suspend fun composeEmail(to: String, subject: String?, body: String?): AutomationResult
}

@Singleton
class AndroidIntentTool @Inject constructor(
    @ApplicationContext private val context: Context
) : IntentTool {

    override suspend fun openUrl(url: String): AutomationResult {
        val normalized = if (url.startsWith("http://") || url.startsWith("https://")) url else "https://$url"
        return launch(Intent(Intent.ACTION_VIEW, Uri.parse(normalized)), "Opened $normalized.", "Couldn't open $normalized.")
    }

    override suspend fun dial(number: String): AutomationResult {
        return launch(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number")), "Opened the dialer for $number.", "Couldn't open the dialer.")
    }

    override suspend fun openContacts(): AutomationResult {
        return launch(Intent(Intent.ACTION_VIEW, android.provider.ContactsContract.Contacts.CONTENT_URI), "Opened Contacts.", "Couldn't open Contacts.")
    }

    override suspend fun share(text: String): AutomationResult {
        val sendIntent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        val chooser = Intent.createChooser(sendIntent, "Share via").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(chooser)
            AutomationResult.ok("Opened the share sheet.")
        } catch (e: ActivityNotFoundException) {
            AutomationResult.failed("No app is available to share with.")
        }
    }

    override suspend fun openMaps(query: String): AutomationResult {
        val uri = Uri.parse("geo:0,0?q=" + Uri.encode(query))
        return launch(Intent(Intent.ACTION_VIEW, uri), "Opening Maps for '$query'.", "Couldn't open Maps.")
    }

    override suspend fun composeEmail(to: String, subject: String?, body: String?): AutomationResult {
        val uri = Uri.parse("mailto:" + Uri.encode(to))
        val intent = Intent(Intent.ACTION_SENDTO, uri).apply {
            subject?.let { putExtra(Intent.EXTRA_SUBJECT, it) }
            body?.let { putExtra(Intent.EXTRA_TEXT, it) }
        }
        return launch(intent, "Composing an email to $to.", "Couldn't open an email app.")
    }

    private fun launch(intent: Intent, successSummary: String, failureSummary: String): AutomationResult {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            AutomationResult.ok(successSummary)
        } catch (e: ActivityNotFoundException) {
            AutomationResult.failed(failureSummary)
        }
    }
}
