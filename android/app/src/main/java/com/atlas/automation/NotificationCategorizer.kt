package com.atlas.automation

/**
 * Phase 10: Notification Intelligence (mission brief section 10).
 *
 * "Do not blindly send every notification to the LLM. Introduce
 * filtering/routing." This is the routing half: a small, deterministic,
 * package-name/keyword classifier - no LLM call, no network, runs
 * entirely on-device against data already visible to
 * AtlasNotificationListenerService.
 *
 * Same "explainable rules over a model" philosophy as the backend's
 * MemoryLifecycleService/ranking.py - a wrong category here is a
 * one-line rule fix, not a retrain. Deliberately conservative about
 * IMPORTANT: only unambiguous categories (alarms, calendar, SMS/calls)
 * are auto-classified that way; everything not matched falls to UNKNOWN
 * rather than being guessed into a category that might make a user
 * over-trust a filtered view.
 */
enum class NotificationCategory {
    IMPORTANT,
    ROUTINE,
    PROMOTIONAL,
    SYSTEM,
    PERSONAL,
    UNKNOWN
}

object NotificationCategorizer {

    private val SYSTEM_PACKAGE_PREFIXES = listOf(
        "android", "com.android.", "com.google.android.gms", "com.google.android.gsf"
    )
    private val IMPORTANT_PACKAGE_KEYWORDS = listOf(
        "alarm", "clock", "calendar", "phone", "dialer", "contacts"
    )
    private val PERSONAL_PACKAGE_KEYWORDS = listOf(
        "messag", "sms", "mms", "whatsapp", "telegram", "signal", "gmail", "mail", "outlook", "slack", "teams", "chat", "hangouts", "messenger"
    )
    private val PROMOTIONAL_TEXT_KEYWORDS = listOf(
        "% off", "sale", "deal", "discount", "limited time", "coupon", "offer ends",
        "free shipping", "clearance", "buy one", "flash sale"
    )
    private val ROUTINE_PACKAGE_KEYWORDS = listOf(
        "weather", "fitness", "health", "step", "news", "podcast", "music", "spotify"
    )

    /**
     * `packageName` is authoritative where possible (it can't be spoofed
     * by notification text the way title/text can); title/text are only
     * consulted for the PROMOTIONAL keyword check, since promotional
     * content isn't tied to a fixed set of packages the way "this is the
     * Phone app" is.
     *
     * IMPORTANT/PERSONAL keyword checks deliberately run *before* the
     * SYSTEM prefix check, not after: several genuinely important AOSP
     * packages (e.g. the stock dialer, "com.android.dialer") live under
     * the same "com.android."/"android" prefixes as generic system
     * packages like "com.android.systemui". Checking SYSTEM first would
     * swallow the stock phone/messaging apps into SYSTEM before their
     * IMPORTANT/PERSONAL keywords were ever consulted - exactly the
     * "SMS/calls should be IMPORTANT" case this class's own docstring
     * names as unambiguous.
     */
    fun categorize(packageName: String, title: String?, text: String?): NotificationCategory {
        val pkg = packageName.lowercase()

        if (IMPORTANT_PACKAGE_KEYWORDS.any { pkg.contains(it) }) return NotificationCategory.IMPORTANT
        // Gmail's real package id is "com.google.android.gm" (Google
        // truncated it) - it contains neither "gmail" nor "mail", so it
        // needs its own precise check. A plain "contains" keyword for
        // this (e.g. "android.gm") would also match
        // "com.google.android.gms" (Play Services) as a false positive,
        // since that string literally contains "android.gm" as a
        // substring - endsWith is exact where contains is not.
        if (PERSONAL_PACKAGE_KEYWORDS.any { pkg.contains(it) } || pkg.endsWith(".gm")) return NotificationCategory.PERSONAL
        if (SYSTEM_PACKAGE_PREFIXES.any { pkg.startsWith(it) }) return NotificationCategory.SYSTEM

        val combinedText = listOfNotNull(title, text).joinToString(" ").lowercase()
        if (combinedText.isNotBlank() && PROMOTIONAL_TEXT_KEYWORDS.any { combinedText.contains(it) }) {
            return NotificationCategory.PROMOTIONAL
        }

        if (ROUTINE_PACKAGE_KEYWORDS.any { pkg.contains(it) }) return NotificationCategory.ROUTINE

        return NotificationCategory.UNKNOWN
    }
}
