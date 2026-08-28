package com.atlas.data.repository

import com.atlas.api.AtlasApiService
import com.atlas.data.models.CreateMemoryRequest
import com.atlas.data.models.MemoryDto
import com.atlas.data.models.UpdateMemoryRequest
import retrofit2.Response
import javax.inject.Inject
import javax.inject.Singleton

interface MemoryRepository {
    suspend fun listMemories(
        memoryType: String? = null,
        category: String? = null,
        tag: String? = null,
        importance: Int? = null,
        isPinned: Boolean? = null,
        skip: Int = 0,
        limit: Int = 100
    ): Result<List<MemoryDto>>

    suspend fun searchMemories(
        query: String,
        memoryType: String? = null,
        limit: Int = 50
    ): Result<List<MemoryDto>>

    suspend fun getMemory(memoryId: String): Result<MemoryDto>
    suspend fun createMemory(request: CreateMemoryRequest): Result<MemoryDto>
    suspend fun updateMemory(memoryId: String, request: UpdateMemoryRequest): Result<MemoryDto>
    suspend fun deleteMemory(memoryId: String): Result<MemoryDto>
}

@Singleton
class MemoryRepositoryImpl @Inject constructor(
    private val apiService: AtlasApiService
) : MemoryRepository {

    override suspend fun listMemories(
        memoryType: String?,
        category: String?,
        tag: String?,
        importance: Int?,
        isPinned: Boolean?,
        skip: Int,
        limit: Int
    ): Result<List<MemoryDto>> = safeCall {
        apiService.listMemories(
            memoryType = memoryType,
            category = category,
            tag = tag,
            importance = importance,
            isPinned = isPinned,
            skip = skip,
            limit = limit
        )
    }

    override suspend fun searchMemories(
        query: String,
        memoryType: String?,
        limit: Int
    ): Result<List<MemoryDto>> = safeCall {
        apiService.searchMemories(query = query, memoryType = memoryType, limit = limit)
    }

    override suspend fun getMemory(memoryId: String): Result<MemoryDto> = safeCall {
        apiService.getMemory(memoryId)
    }

    override suspend fun createMemory(request: CreateMemoryRequest): Result<MemoryDto> = safeCall {
        apiService.createMemory(request)
    }

    override suspend fun updateMemory(memoryId: String, request: UpdateMemoryRequest): Result<MemoryDto> = safeCall {
        apiService.updateMemory(memoryId, request)
    }

    override suspend fun deleteMemory(memoryId: String): Result<MemoryDto> = safeCall {
        apiService.deleteMemory(memoryId)
    }

    private suspend fun <T> safeCall(call: suspend () -> Response<T>): Result<T> {
        return try {
            val response = call()
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(body)
            } else {
                Result.failure(Exception("API Error: ${response.code()} ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
