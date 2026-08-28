package com.atlas.automation

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ResolveInfo
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation - Application Manager module.
 *
 * Implements launch / search / foreground-app-detection using only the
 * official android.content.pm.PackageManager APIs, scoped to apps that
 * declare a LAUNCHER activity (see the <queries> block in
 * AndroidManifest.xml) - deliberately not the QUERY_ALL_PACKAGES
 * permission, which Play Store restricts to apps with a launcher/app-store
 * use case ATLAS doesn't have.
 *
 * Foreground-app detection piggybacks on AccessibilityBridge's
 * window-state tracking instead of requiring the separate, more sensitive
 * PACKAGE_USAGE_STATS permission (which additionally can't be granted via
 * a normal runtime prompt - it needs a special Settings screen). This
 * means foreground-app detection is only as fresh as the last window
 * change the Accessibility Service observed, and is unavailable until that
 * service has been enabled at least once - see
 * docs/Phase8_KnownLimitations.md.
 */
interface AppManager {
    suspend fun launchApp(query: String): AutomationResult
    suspend fun searchApps(query: String): AutomationResult
    fun foregroundApp(): String?
}

@Singleton
class AndroidAppManager @Inject constructor(
    @ApplicationContext private val context: Context,
    private val accessibilityBridge: AccessibilityBridge
) : AppManager {

    private val packageManager: PackageManager get() = context.packageManager

    override suspend fun launchApp(query: String): AutomationResult {
        val apps = installedLaunchableApps()
        val match = bestMatch(apps, query) ?: return AutomationResult.failed(
            "No app matching '$query' was found on this device."
        )
        val launchIntent = packageManager.getLaunchIntentForPackage(match.packageName)
            ?: return AutomationResult.failed("Found '${match.label}' but it has no launchable activity.")
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(launchIntent)
            AutomationResult.ok("Opened ${match.label}.", details = mapOf("package" to match.packageName))
        } catch (e: Exception) {
            AutomationResult.failed("Found '${match.label}' but couldn't open it: ${e.message}")
        }
    }

    override suspend fun searchApps(query: String): AutomationResult {
        val apps = installedLaunchableApps()
        val matches = apps.filter { it.label.contains(query, ignoreCase = true) }
            .sortedBy { it.label.lowercase() }
        if (matches.isEmpty()) {
            return AutomationResult.failed("No installed apps match '$query'.")
        }
        val summary = "Found ${matches.size} app${if (matches.size == 1) "" else "s"}: " +
            matches.take(10).joinToString(", ") { it.label }
        return AutomationResult.ok(summary, details = mapOf("count" to matches.size.toString()))
    }

    override fun foregroundApp(): String? {
        val packageName = accessibilityBridge.foregroundPackage.value ?: return null
        return try {
            packageManager.getApplicationLabel(packageManager.getApplicationInfo(packageName, 0)).toString()
        } catch (e: PackageManager.NameNotFoundException) {
            packageName
        }
    }

    private fun installedLaunchableApps(): List<AppInfo> {
        val launcherIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val resolved: List<ResolveInfo> = packageManager.queryIntentActivities(launcherIntent, 0)
        return resolved.mapNotNull { info ->
            val packageName = info.activityInfo?.packageName ?: return@mapNotNull null
            val label = info.loadLabel(packageManager)?.toString() ?: return@mapNotNull null
            AppInfo(packageName = packageName, label = label)
        }.distinctBy { it.packageName }
    }

    /** Exact (case-insensitive) match wins; otherwise the shortest label
     * that starts with the query, so "maps" prefers "Maps" over
     * "Maps - Navigate & Explore" if both are installed; otherwise falls
     * back to the shortest label containing the query anywhere. */
    private fun bestMatch(apps: List<AppInfo>, query: String): AppInfo? {
        val needle = query.trim()
        if (needle.isEmpty()) return null
        apps.firstOrNull { it.label.equals(needle, ignoreCase = true) }?.let { return it }
        apps.filter { it.label.startsWith(needle, ignoreCase = true) }
            .minByOrNull { it.label.length }
            ?.let { return it }
        return apps.filter { it.label.contains(needle, ignoreCase = true) }
            .minByOrNull { it.label.length }
    }
}
