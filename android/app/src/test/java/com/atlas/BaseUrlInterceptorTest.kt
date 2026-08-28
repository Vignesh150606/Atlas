package com.atlas

import com.atlas.data.local.ServerConfigProvider
import com.atlas.di.BaseUrlInterceptor
import okhttp3.Request
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Phase 12 (docs/MASTER_PLAN.md #2.1). Same hand-written FakeChain (see
 * InterceptorFakes.kt) as ApiKeyInterceptorTest.kt - no mocking library
 * in this project.
 */
private class FakeServerConfigProvider(private val baseUrl: String) : ServerConfigProvider {
    override fun getBaseUrl(): String = baseUrl
}

class BaseUrlInterceptorTest {

    @Test
    fun rewritesSchemeHostAndPortToConfiguredServer() {
        val interceptor = BaseUrlInterceptor(FakeServerConfigProvider("https://atlas.example.com"))
        val request = Request.Builder().url("http://retrofit-placeholder.invalid/api/v1/chat").build()
        val chain = FakeChain(request)

        interceptor.intercept(chain)

        val seen = chain.seenRequest!!.url
        assertEquals("https", seen.scheme)
        assertEquals("atlas.example.com", seen.host)
        assertEquals(443, seen.port) // default HTTPS port, since none was specified
        assertEquals("/api/v1/chat", seen.encodedPath)
    }

    @Test
    fun preservesExplicitPortWhenConfigured() {
        val interceptor = BaseUrlInterceptor(FakeServerConfigProvider("http://10.0.2.2:8000"))
        val request = Request.Builder().url("http://retrofit-placeholder.invalid/api/v1/health").build()
        val chain = FakeChain(request)

        interceptor.intercept(chain)

        val seen = chain.seenRequest!!.url
        assertEquals("http", seen.scheme)
        assertEquals("10.0.2.2", seen.host)
        assertEquals(8000, seen.port)
        assertEquals("/api/v1/health", seen.encodedPath)
    }

    @Test
    fun preservesQueryParametersAndPath() {
        val interceptor = BaseUrlInterceptor(FakeServerConfigProvider("https://atlas.example.com"))
        val request = Request.Builder()
            .url("http://retrofit-placeholder.invalid/api/v1/memory/search?q=coffee&limit=10")
            .build()
        val chain = FakeChain(request)

        interceptor.intercept(chain)

        val seen = chain.seenRequest!!.url
        assertEquals("/api/v1/memory/search", seen.encodedPath)
        assertEquals("q=coffee&limit=10", seen.encodedQuery)
    }

    @Test
    fun leavesRequestUnmodifiedWhenConfiguredUrlIsUnparseable() {
        val interceptor = BaseUrlInterceptor(FakeServerConfigProvider("not a url"))
        val request = Request.Builder().url("http://retrofit-placeholder.invalid/api/v1/chat").build()
        val chain = FakeChain(request)

        interceptor.intercept(chain)

        assertEquals(request.url, chain.seenRequest!!.url)
    }
}
