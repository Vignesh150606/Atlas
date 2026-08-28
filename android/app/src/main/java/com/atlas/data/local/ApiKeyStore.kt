package com.atlas.data.local

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Read-only view used by ApiKeyInterceptor. Split out from ApiKeyStore
 * so interceptor tests can fake this one small method instead of
 * needing a real Android Context (this is a plain JVM src/test unit
 * test, and this project has no Robolectric dependency - see
 * ApiKeyInterceptorTest.kt).
 */
interface ApiKeyProvider {
    fun getApiKey(): String?
}

/**
 * Phase 11: persists the optional shared API key (see backend
 * Settings.API_KEY / app/core/deps.py::verify_api_key) across app
 * restarts.
 *
 * Plain SharedPreferences rather than androidx.datastore: this app has
 * no local-settings persistence subsystem at all yet (every existing
 * repository is a pure Retrofit pass-through - see AppModule.kt), and a
 * single string preference doesn't need DataStore's async/Flow API or
 * its extra Gradle dependency. If a second setting needing real
 * persistence shows up, that's the point to introduce DataStore and
 * migrate this - not before.
 */
@Singleton
class ApiKeyStore @Inject constructor(@ApplicationContext context: Context) : ApiKeyProvider {

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    override fun getApiKey(): String? = prefs.getString(KEY_API_KEY, null)?.takeIf { it.isNotBlank() }

    fun setApiKey(key: String?) {
        prefs.edit().apply {
            if (key.isNullOrBlank()) remove(KEY_API_KEY) else putString(KEY_API_KEY, key.trim())
        }.apply()
    }

    companion object {
        private const val PREFS_NAME = "atlas_settings"
        private const val KEY_API_KEY = "api_key"
    }
}
