package com.atlas.data.local

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 12 (docs/MASTER_PLAN.md #2.1, the CRITICAL finding): the backend
 * URL used to be `BuildConfig.API_BASE_URL`, a compile-time constant
 * hardcoded to a developer's own LAN IP - not reachable from mobile data,
 * not reachable once that IP is reassigned by DHCP, and not even reachable
 * over the developer's own Wi-Fi at the time of the audit, because that IP
 * was never added to src/debug/res/xml/network_security_config.xml's
 * cleartext allow-list. Every request from the installed APK failed.
 *
 * This makes the server URL a runtime setting instead: editable from
 * Settings (see ui/screens/settings/), read here, and applied per-request
 * by BaseUrlInterceptor rather than baked into the Retrofit instance at
 * injection time. Changing it takes effect on the very next request - no
 * rebuild, no reinstall.
 *
 * Read-only ServerConfigProvider / read-write ServerConfigStore split
 * mirrors ApiKeyStore/ApiKeyProvider exactly, for the same reason: a
 * plain-JVM interceptor unit test can fake the read-only interface
 * without a real Android Context.
 */
interface ServerConfigProvider {
    /** Scheme + host[:port] only, e.g. "https://atlas.example.com" or
     * "http://10.0.2.2:8000" - no path. BaseUrlInterceptor keeps whatever
     * path Retrofit already built (the API's own /api/v1/... structure)
     * and only replaces scheme/host/port, so this deliberately does not
     * ask the user to also get the API path right. */
    fun getBaseUrl(): String
}

@Singleton
class ServerConfigStore @Inject constructor(@ApplicationContext context: Context) : ServerConfigProvider {

    // Phase 12 / SECURITY_PLAN.md S4: encrypted at rest, same as
    // ApiKeyStore (see EncryptedPrefs.kt) - the server URL is less
    // sensitive than the API key, but sharing one encrypted file for both
    // settings is simpler than maintaining two different storage
    // mechanisms for what is, to the user, one "Settings" screen.
    private val prefs = EncryptedPrefs.create(context, PREFS_NAME)

    override fun getBaseUrl(): String =
        prefs.getString(KEY_BASE_URL, null)?.takeIf { it.isNotBlank() } ?: DEFAULT_BASE_URL

    fun setBaseUrl(url: String?) {
        prefs.edit().apply {
            if (url.isNullOrBlank()) remove(KEY_BASE_URL) else putString(KEY_BASE_URL, url.trim().trimEnd('/'))
        }.apply()
    }

    /** Whether the user has ever explicitly set a URL - so Settings can
     * show "(default, emulator only)" versus a value they actually chose. */
    fun hasExplicitBaseUrl(): Boolean = prefs.getString(KEY_BASE_URL, null)?.isNotBlank() == true

    companion object {
        private const val PREFS_NAME = "atlas_settings"
        private const val KEY_BASE_URL = "server_base_url"

        // 10.0.2.2 is the Android Emulator's alias for the host machine's
        // localhost - see src/debug/res/xml/network_security_config.xml,
        // which allows cleartext to exactly this host (plus localhost/
        // 127.0.0.1) for debug builds. This is a deliberately safe,
        // functional-out-of-the-box default for emulator development; it
        // is NOT reachable from a physical device or from mobile data.
        // A real deployment's HTTPS URL must be entered in Settings - see
        // ServerConfigStore's class doc and docs/DEPLOYMENT_PLAN.md.
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"
    }
}
