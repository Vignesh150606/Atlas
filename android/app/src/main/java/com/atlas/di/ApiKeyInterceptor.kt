package com.atlas.di

import com.atlas.data.local.ApiKeyProvider
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

/**
 * Phase 11: attaches the "X-API-Key" header (matching the backend's
 * app.core.deps.verify_api_key) to every request when a key is
 * configured in Settings. A no-op - the request passes through
 * unmodified - when nothing is stored, matching the backend's own
 * "unset means open" default so a fresh install talking to a fresh
 * (also-unconfigured) backend needs no setup.
 */
class ApiKeyInterceptor @Inject constructor(
    private val apiKeyProvider: ApiKeyProvider
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val apiKey = apiKeyProvider.getApiKey()
        val request = if (apiKey != null) {
            original.newBuilder().addHeader("X-API-Key", apiKey).build()
        } else {
            original
        }
        return chain.proceed(request)
    }
}
