package com.atlas.automation

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation - Permission Center support.
 *
 * Reads the *actual* current status of each permission Permission Center
 * shows, straight from the platform, rather than from
 * AccessibilityBridge.isConnected / NotificationBridge.isConnected. Those
 * two only reflect "has our service been bound at least once this process
 * lifetime," which lags behind the user flipping the system toggle (the OS
 * doesn't necessarily rebind instantly, and never un-binds if the process
 * hasn't been revisited) - not accurate enough for a settings screen the
 * user checks immediately after coming back from system Settings.
 */
interface PermissionStatusChecker {
    fun isAccessibilityServiceEnabled(): Boolean
    fun isNotificationListenerEnabled(): Boolean
    fun isMicrophoneGranted(): Boolean
    fun isNotificationPermissionGranted(): Boolean
}

@Singleton
class AndroidPermissionStatusChecker @Inject constructor(
    @ApplicationContext private val context: Context
) : PermissionStatusChecker {

    override fun isAccessibilityServiceEnabled(): Boolean {
        val expected = ComponentName(context, AtlasAccessibilityService::class.java).flattenToString()
        val enabled = Settings.Secure.getString(
            context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        // Colon-separated component names, e.g. "com.foo/.Bar:com.atlas/.automation.AtlasAccessibilityService".
        return enabled.split(':').any { it.equals(expected, ignoreCase = true) }
    }

    override fun isNotificationListenerEnabled(): Boolean {
        return context.packageName in NotificationManagerCompat.getEnabledListenerPackages(context)
    }

    override fun isMicrophoneGranted(): Boolean {
        return ContextCompat.checkSelfPermission(
            context, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Phase 11 section 2 (Proactive Suggestions). POST_NOTIFICATIONS only
     * exists as a runtime permission from API 33 (Tiramisu) onward -
     * below that, posting a notification needs no explicit grant, so
     * this is unconditionally true there rather than checking a
     * permission string that doesn't apply.
     */
    override fun isNotificationPermissionGranted(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            context, Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
    }
}
