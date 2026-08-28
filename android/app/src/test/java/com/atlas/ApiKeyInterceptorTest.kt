package com.atlas

import com.atlas.data.local.ApiKeyProvider
import com.atlas.di.ApiKeyInterceptor
import okhttp3.Interceptor
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.util.concurrent.TimeUnit

/**
 * Phase 11. No mocking library exists in this project (see every other
 * *Test.kt / Fake*.kt file, e.g. VoiceEngineFakes.kt) - a minimal
 * hand-written fake Chain instead of introducing Mockito/MockK for one
 * interceptor.
 */
private class FakeChain(private val request: Request) : Interceptor.Chain {
    var seenRequest: Request? = null

    override fun request(): Request = request
    override fun proceed(request: Request): Response {
        seenRequest = request
        return Response.Builder()
            .request(request)
            .protocol(Protocol.HTTP_1_1)
            .code(200)
            .message("OK")
            .body("".toResponseBody(null))
            .build()
    }

    override fun connection() = null
    override fun call(): okhttp3.Call = throw UnsupportedOperationException("not needed for this test")
    override fun connectTimeoutMillis() = 0
    override fun withConnectTimeout(timeout: Int, unit: TimeUnit) = this
    override fun readTimeoutMillis() = 0
    override fun withReadTimeout(timeout: Int, unit: TimeUnit) = this
    override fun writeTimeoutMillis() = 0
    override fun withWriteTimeout(timeout: Int, unit: TimeUnit) = this
}

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
