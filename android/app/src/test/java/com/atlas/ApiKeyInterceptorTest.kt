package com.atlas

import com.atlas.data.local.ApiKeyProvider
import com.atlas.di.ApiKeyInterceptor
import okhttp3.Request
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Phase 11. No mocking library exists in this project (see every other
 * *Test.kt / Fake*.kt file, e.g. VoiceEngineFakes.kt) - a minimal
 * hand-written fake Chain (FakeChain, see InterceptorFakes.kt) instead of
 * introducing Mockito/MockK for one interceptor.
 */
private class FakeApiKeyProvider(private val key: String?) : ApiKeyProvider {
    override fun getApiKey(): String? = key
}

class ApiKeyInterceptorTest {

    @Test
    fun testAddsHeaderWhenKeyIsConfigured() {
        val interceptor = ApiKeyInterceptor(FakeApiKeyProvider("secret-123"))
        val request = Request.Builder().url("http://localhost/api/v1/reminders").build()
        val chain = FakeChain(request)

        interceptor.intercept(chain)

        assertEquals("secret-123", chain.seenRequest?.header("X-API-Key"))
    }

    @Test
    fun testLeavesRequestUnmodifiedWhenNoKeyConfigured() {
        val interceptor = ApiKeyInterceptor(FakeApiKeyProvider(null))
        val request = Request.Builder().url("http://localhost/api/v1/reminders").build()
        val chain = FakeChain(request)

        interceptor.intercept(chain)

        assertNull(chain.seenRequest?.header("X-API-Key"))
    }
}
