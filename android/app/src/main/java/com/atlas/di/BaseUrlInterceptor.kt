package com.atlas.di

import com.atlas.data.local.ServerConfigProvider
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

/**
 * Phase 12 (docs/MASTER_PLAN.md #2.1): rewrites every request's
 * scheme/host/port to the currently-configured server (see
 * ServerConfigStore) before it goes out, leaving the path Retrofit
 * already built (/api/v1/...) untouched. Retrofit itself is built once,
 * at injection time, against a fixed placeholder baseUrl (see
 * AppModule.provideRetrofit) - this interceptor is what actually makes
 * the server address change take effect immediately, without rebuilding
 * the Retrofit/OkHttp graph, the moment the user saves a new URL in
 * Settings.
 *
 * Runs as an application interceptor (added via
 * OkHttpClient.Builder.addInterceptor, not addNetworkInterceptor), so it
 * executes before DNS resolution / connection - the placeholder host in
 * the Retrofit baseUrl is never actually looked up or connected to.
 *
 * If the configured value fails to parse as a URL (e.g. the user typed
 * garbage into Settings), this deliberately falls back to leaving the
 * request untouched rather than throwing - a broken saved value should
 * degrade to "requests fail with a normal connection error the user can
 * see", not crash the interceptor chain.
 */
class BaseUrlInterceptor @Inject constructor(
    private val serverConfigProvider: ServerConfigProvider
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val configured = serverConfigProvider.getBaseUrl().toHttpUrlOrNull()
            ?: return chain.proceed(original)

        val rewritten = original.url.newBuilder()
            .scheme(configured.scheme)
            .host(configured.host)
            .port(configured.port)
            .build()

        return chain.proceed(original.newBuilder().url(rewritten).build())
    }
}
