package com.atlas.data.repository

import com.atlas.api.AtlasApiService
import com.atlas.api.HealthResponse
import com.atlas.data.models.ChatRequest
import com.atlas.data.models.ChatResponse
import com.atlas.data.models.DeviceActionResultRequest
import com.atlas.data.models.DeviceActionResultResponse
import javax.inject.Inject
import javax.inject.Singleton

interface ChatRepository {
    suspend fun checkHealth(): Result<HealthResponse>
    suspend fun sendMessage(message: String, conversationId: Int? = null): Result<ChatResponse>

    /**
     * Phase 8: reports the outcome of a locally-executed ChatResponse.device_action
     * back to the backend. See AtlasApiService.reportDeviceResult.
     */
    suspend fun reportDeviceAction(request: DeviceActionResultRequest): Result<DeviceActionResultResponse>
}

@Singleton
class ChatRepositoryImpl @Inject constructor(
    private val apiService: AtlasApiService
) : ChatRepository {

    override suspend fun checkHealth(): Result<HealthResponse> {
        return try {
            val response = apiService.checkHealth()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Health check failed with code ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun sendMessage(message: String, conversationId: Int?): Result<ChatResponse> {
        return try {
            val request = ChatRequest(message = message, conversationId = conversationId)
            val response = apiService.sendMessage(request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("API Error: ${response.code()} ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun reportDeviceAction(request: DeviceActionResultRequest): Result<DeviceActionResultResponse> {
        return try {
            val response = apiService.reportDeviceResult(request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("API Error: ${response.code()} ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
