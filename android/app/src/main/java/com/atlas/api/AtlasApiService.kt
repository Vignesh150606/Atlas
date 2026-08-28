package com.atlas.api

import com.atlas.data.models.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface AtlasApiService {
    @GET("health")
    suspend fun checkHealth(): Response<HealthResponse>

    @POST("chat")
    suspend fun sendMessage(@Body request: ChatRequest): Response<ChatResponse>

    // Phase 8: Android Automation Foundation. Reports the outcome of a
    // ChatResponse.device_action that was executed locally back to the
    // backend (closes the "Android Tool -> Result -> Memory" loop - see
    // app/api/v1/endpoints/chat.py::report_device_result).
    @POST("chat/device-result")
    suspend fun reportDeviceResult(@Body request: DeviceActionResultRequest): Response<DeviceActionResultResponse>

    // Memory APIs
    @POST("memory")
    suspend fun createMemory(@Body request: CreateMemoryRequest): Response<MemoryDto>

    @GET("memory")
    suspend fun listMemories(
        @Query("memory_type") memoryType: String? = null,
        @Query("category") category: String? = null,
        @Query("tag") tag: String? = null,
        @Query("importance") importance: Int? = null,
        @Query("is_pinned") isPinned: Boolean? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 100
    ): Response<List<MemoryDto>>

    @GET("memory/search")
    suspend fun searchMemories(
        @Query("q") query: String,
        @Query("memory_type") memoryType: String? = null,
        @Query("limit") limit: Int = 50
    ): Response<List<MemoryDto>>

    @GET("memory/{id}")
    suspend fun getMemory(@Path("id") memoryId: String): Response<MemoryDto>

    @PATCH("memory/{id}")
    suspend fun updateMemory(
        @Path("id") memoryId: String,
        @Body request: UpdateMemoryRequest
    ): Response<MemoryDto>

    @DELETE("memory/{id}")
    suspend fun deleteMemory(@Path("id") memoryId: String): Response<MemoryDto>

    // Document APIs (Phase 6)
    @Multipart
    @POST("documents")
    suspend fun uploadDocument(
        @Part file: MultipartBody.Part,
        @Part("title") title: RequestBody? = null,
        @Part("tags") tags: RequestBody? = null,
        @Part("author") author: RequestBody? = null
    ): Response<DocumentDto>

    @GET("documents")
    suspend fun listDocuments(
        @Query("file_type") fileType: String? = null,
        @Query("source") source: String? = null,
        @Query("tag") tag: String? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 100
    ): Response<List<DocumentSummaryDto>>

    @GET("documents/search")
    suspend fun searchDocuments(
        @Query("q") query: String,
        @Query("file_type") fileType: String? = null,
        @Query("limit") limit: Int = 50
    ): Response<List<DocumentSummaryDto>>

    @GET("documents/{id}")
    suspend fun getDocument(@Path("id") documentId: String): Response<DocumentDto>

    @GET("documents/{id}/entities")
    suspend fun getDocumentEntities(@Path("id") documentId: String): Response<List<EntityDto>>

    @PATCH("documents/{id}")
    suspend fun updateDocument(
        @Path("id") documentId: String,
        @Body request: DocumentUpdateRequest
    ): Response<DocumentDto>

    @DELETE("documents/{id}")
    suspend fun deleteDocument(@Path("id") documentId: String): Response<DocumentDto>

    // Knowledge APIs (Phase 6)
    @GET("knowledge/entities")
    suspend fun listEntities(
        @Query("entity_type") entityType: String? = null,
        @Query("document_id") documentId: String? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 200
    ): Response<List<EntityDto>>

    @GET("knowledge/search")
    suspend fun searchKnowledge(
        @Query("q") query: String,
        @Query("limit") limit: Int = 10
    ): Response<KnowledgeSearchResultDto>

    @GET("knowledge/timeline")
    suspend fun getTimeline(@Query("limit") limit: Int = 100): Response<TimelineResponseDto>

    // --- Phase 10: Personal Assistant & Proactive Intelligence -----------
    // Reminders (app/api/v1/endpoints/reminders.py)
    @POST("reminders")
    suspend fun createReminder(@Body request: CreateReminderRequest): Response<ReminderDto>

    @POST("reminders/from-text")
    suspend fun createReminderFromText(@Body request: CreateReminderFromTextRequest): Response<ReminderDto>

    @GET("reminders")
    suspend fun listReminders(
        @Query("status") status: String? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 100
    ): Response<List<ReminderDto>>

    @GET("reminders/upcoming")
    suspend fun listUpcomingReminders(@Query("within_hours") withinHours: Int = 24): Response<List<ReminderDto>>

    @GET("reminders/{id}")
    suspend fun getReminder(@Path("id") reminderId: String): Response<ReminderDto>

    @POST("reminders/{id}/complete")
    suspend fun completeReminder(@Path("id") reminderId: String): Response<ReminderDto>

    @POST("reminders/{id}/cancel")
    suspend fun cancelReminder(@Path("id") reminderId: String): Response<ReminderDto>

    @DELETE("reminders/{id}")
    suspend fun deleteReminder(@Path("id") reminderId: String): Response<ReminderDto>

    // Tasks (app/api/v1/endpoints/tasks.py)
    @POST("tasks")
    suspend fun createTask(@Body request: CreateTaskRequest): Response<TaskDto>

    @GET("tasks")
    suspend fun listTasks(
        @Query("status") status: String? = null,
        @Query("priority") priority: String? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 100
    ): Response<List<TaskDto>>

    @POST("tasks/{id}/complete")
    suspend fun completeTask(@Path("id") taskId: String): Response<TaskDto>

    @POST("tasks/{id}/cancel")
    suspend fun cancelTask(@Path("id") taskId: String): Response<TaskDto>

    @POST("tasks/{id}/prioritize")
    suspend fun prioritizeTask(@Path("id") taskId: String, @Body request: PrioritizeTaskRequest): Response<TaskDto>

    @DELETE("tasks/{id}")
    suspend fun deleteTask(@Path("id") taskId: String): Response<TaskDto>

    // Routines (app/api/v1/endpoints/routines.py)
    @POST("routines")
    suspend fun createRoutine(@Body request: CreateRoutineRequest): Response<RoutineDto>

    @GET("routines")
    suspend fun listRoutines(
        @Query("is_active") isActive: Boolean? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 100
    ): Response<List<RoutineDto>>

    @PATCH("routines/{id}")
    suspend fun updateRoutine(@Path("id") routineId: String, @Body request: UpdateRoutineRequest): Response<RoutineDto>

    @DELETE("routines/{id}")
    suspend fun deleteRoutine(@Path("id") routineId: String): Response<RoutineDto>

    // Daily briefing + proactive suggestions (app/api/v1/endpoints/briefing.py)
    @GET("briefing/daily")
    suspend fun getDailyBriefing(@Query("within_hours") withinHours: Int = 24): Response<DailyBriefingDto>

    @GET("briefing/suggestions")
    suspend fun getProactiveSuggestions(): Response<ProactiveSuggestionsDto>
}

data class HealthResponse(
    val status: String,
    val version: String,
    val database: String? = null
)
