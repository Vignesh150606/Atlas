package com.atlas

import okhttp3.Interceptor
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import java.util.concurrent.TimeUnit

/**
 * Phase 11/12: shared hand-written fake OkHttp Chain, used by
 * ApiKeyInterceptorTest and BaseUrlInterceptorTest. No mocking library
 * exists in this project (see every other *Fakes.kt file, e.g.
 * AutomationFakes.kt, VoiceEngineFakes.kt) - this was previously
 * duplicated privately inside ApiKeyInterceptorTest.kt; extracted here
 * once a second interceptor test needed the exact same fake.
 */
class FakeChain(private val request: Request) : Interceptor.Chain {
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
