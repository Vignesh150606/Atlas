package com.atlas

import com.atlas.automation.NotificationCategory
import com.atlas.automation.NotificationCategorizer
import org.junit.Assert.*
import org.junit.Test

/**
 * Phase 10: NotificationCategorizer is pure Kotlin (no Android framework
 * dependency - no Context, no StatusBarNotification), so unlike
 * AtlasNotificationListenerService itself it's directly unit-testable
 * without Robolectric or an emulator.
 */
class NotificationCategorizerTest {

    @Test
    fun testSystemPackagesAreCategorizedAsSystem() {
        assertEquals(NotificationCategory.SYSTEM, NotificationCategorizer.categorize("com.android.systemui", null, null))
        assertEquals(NotificationCategory.SYSTEM, NotificationCategorizer.categorize("android", null, null))
        assertEquals(NotificationCategory.SYSTEM, NotificationCategorizer.categorize("com.google.android.gms", null, null))
    }

    @Test
    fun testAlarmAndCalendarPackagesAreImportant() {
        assertEquals(NotificationCategory.IMPORTANT, NotificationCategorizer.categorize("com.google.android.deskclock", "Alarm", "Wake up"))
        assertEquals(NotificationCategory.IMPORTANT, NotificationCategorizer.categorize("com.google.android.calendar", "Meeting", "Starts in 10 min"))
        assertEquals(NotificationCategory.IMPORTANT, NotificationCategorizer.categorize("com.android.dialer", "Missed call", "Mom"))
    }

    @Test
    fun testMessagingPackagesArePersonal() {
        assertEquals(NotificationCategory.PERSONAL, NotificationCategorizer.categorize("com.whatsapp", "Alice", "Hey!"))
        assertEquals(NotificationCategory.PERSONAL, NotificationCategorizer.categorize("com.google.android.gm", "Bob", "Re: invoice"))
        assertEquals(NotificationCategory.PERSONAL, NotificationCategorizer.categorize("com.slack", "team-general", "New message"))
    }

    @Test
    fun testPromotionalKeywordsInTextAreDetected() {
        assertEquals(
            NotificationCategory.PROMOTIONAL,
            NotificationCategorizer.categorize("com.somestore.app", "Flash Sale!", "50% off everything today only")
        )
        assertEquals(
            NotificationCategory.PROMOTIONAL,
            NotificationCategorizer.categorize("com.somestore.app", null, "Limited time offer - free shipping")
        )
    }

    @Test
    fun testRoutinePackagesAreCategorizedAsRoutine() {
        assertEquals(NotificationCategory.ROUTINE, NotificationCategorizer.categorize("com.spotify.music", "Now playing", "Some song"))
        assertEquals(NotificationCategory.ROUTINE, NotificationCategorizer.categorize("com.weather.app", "Today", "Sunny, 72F"))
    }

    @Test
    fun testUnrecognizedPackageWithOrdinaryTextIsUnknown() {
        assertEquals(
            NotificationCategory.UNKNOWN,
            NotificationCategorizer.categorize("com.somerandomapp.thing", "Update available", "Version 2.0 is ready")
        )
    }

    @Test
    fun testPackageMatchTakesPriorityOverPromotionalTextKeywords() {
        // A messaging app mentioning "% off" in a personal message (e.g.
        // forwarding a coupon to a friend) should stay PERSONAL - package
        // identity is checked first and is authoritative, since it can't
        // be spoofed by message content the way text can.
        assertEquals(
            NotificationCategory.PERSONAL,
            NotificationCategorizer.categorize("com.whatsapp", "Alice", "Check out this 50% off deal I found")
        )
    }

    @Test
    fun testNullTitleAndTextDoNotCrash() {
        assertEquals(NotificationCategory.UNKNOWN, NotificationCategorizer.categorize("com.unknown.app", null, null))
    }
}
