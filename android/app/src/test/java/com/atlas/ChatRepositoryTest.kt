package com.atlas

import com.atlas.api.AtlasApiService
import com.atlas.api.HealthResponse
import com.atlas.data.models.*
import com.atlas.data.repository.ChatRepositoryImpl
import kotlinx.coroutines.runBlocking
import okhttp3.MultipartBody
import okhttp3.RequestBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class FakeAtlasApiService : AtlasApiService {
    override suspend fun checkHealth(): Response<HealthResponse> {
        return Response.success(HealthResponse(status = "healthy", version = "1.0", database = "connected"))
    }

    override suspend fun sendMessage(request: ChatRequest): Response<ChatResponse> {
        return Response.success(
            ChatResponse(
                response = "ATLAS received: ${request.message}",
                conversationId = request.conversationId ?: 1
            )
        )
    }

    // Phase 8: Android Automation Foundation
    override suspend fun reportDeviceResult(request: DeviceActionResultRequest): Response<DeviceActionResultResponse> {
        return Response.success(
            DeviceActionResultResponse(
                id = 1,
                role = "assistant",
                content = "${if (request.success) "\u2705" else "\u26a0\ufe0f"} ${request.summary}"
            )
        )
    }

    // Memory APIs

    override suspend fun createMemory(request: CreateMemoryRequest): Response<MemoryDto> {
        return Response.success(
            MemoryDto(
                id = "fake-memory-1",
                title = request.title,
                content = request.content,
                memoryType = request.memoryType,
                category = request.category,
                importance = request.importance,
                isPinned = request.isPinned,
                source = request.source,
                tags = request.tags,
                structuredData = request.structuredData
            )
        )
    }

    override suspend fun listMemories(
        memoryType: String?,
        category: String?,
        tag: String?,
        importance: Int?,
        isPinned: Boolean?,
        skip: Int,
        limit: Int
    ): Response<List<MemoryDto>> {
        return Response.success(emptyList())
    }

    override suspend fun searchMemories(
        query: String,
        memoryType: String?,
        limit: Int
    ): Response<List<MemoryDto>> {
        return Response.success(emptyList())
    }

    override suspend fun getMemory(memoryId: String): Response<MemoryDto> {
        return Response.success(
            MemoryDto(
                id = memoryId,
                title = "Fake memory",
                content = "Fake content",
                memoryType = MemoryTypeEnum.FACT.value,
                category = "general",
                importance = 3,
                isPinned = false,
                source = "manual"
            )
        )
    }

    override suspend fun updateMemory(
        memoryId: String,
        request: UpdateMemoryRequest
    ): Response<MemoryDto> {
        return Response.success(
            MemoryDto(
                id = memoryId,
                title = request.title ?: "Fake memory",
                content = request.content ?: "Fake content",
                memoryType = request.memoryType ?: MemoryTypeEnum.FACT.value,
                category = request.category ?: "general",
                importance = request.importance ?: 3,
                isPinned = request.isPinned ?: false,
                source = "manual",
                tags = request.tags ?: emptyList()
            )
        )
    }

    override suspend fun deleteMemory(memoryId: String): Response<MemoryDto> {
        return Response.success(
            MemoryDto(
                id = memoryId,
                title = "Fake memory",
                content = "Fake content",
                memoryType = MemoryTypeEnum.FACT.value,
                category = "general",
                importance = 3,
                isPinned = false,
                source = "manual",
                deletedAt = "fake-deleted-at"
            )
        )
    }

    // Document APIs

    override suspend fun uploadDocument(
        file: MultipartBody.Part,
        title: RequestBody?,
        tags: RequestBody?,
        author: RequestBody?
    ): Response<DocumentDto> {
        return Response.success(
            DocumentDto(
                id = "fake-document-1",
                title = "Fake document",
                source = "upload",
                fileType = DocumentTypeEnum.TXT.value
            )
        )
    }

    override suspend fun listDocuments(
        fileType: String?,
        source: String?,
        tag: String?,
        skip: Int,
        limit: Int
    ): Response<List<DocumentSummaryDto>> {
        return Response.success(emptyList())
    }

    override suspend fun searchDocuments(
        query: String,
        fileType: String?,
        limit: Int
    ): Response<List<DocumentSummaryDto>> {
        return Response.success(emptyList())
    }

    override suspend fun getDocument(documentId: String): Response<DocumentDto> {
        return Response.success(
            DocumentDto(
                id = documentId,
                title = "Fake document",
                source = "upload",
                fileType = DocumentTypeEnum.TXT.value
            )
        )
    }

    override suspend fun getDocumentEntities(documentId: String): Response<List<EntityDto>> {
        return Response.success(emptyList())
    }

    override suspend fun updateDocument(
        documentId: String,
        request: DocumentUpdateRequest
    ): Response<DocumentDto> {
        return Response.success(
            DocumentDto(
                id = documentId,
                title = request.title ?: "Fake document",
                source = "upload",
                fileType = DocumentTypeEnum.TXT.value,
                tags = request.tags ?: emptyList(),
                author = request.author
            )
        )
    }

    override suspend fun deleteDocument(documentId: String): Response<DocumentDto> {
        return Response.success(
            DocumentDto(
                id = documentId,
                title = "Fake document",
                source = "upload",
                fileType = DocumentTypeEnum.TXT.value,
                deletedAt = "fake-deleted-at"
            )
        )
    }

    // Knowledge APIs

    override suspend fun listEntities(
        entityType: String?,
        documentId: String?,
        skip: Int,
        limit: Int
    ): Response<List<EntityDto>> {
        return Response.success(emptyList())
    }

    override suspend fun searchKnowledge(query: String, limit: Int): Response<KnowledgeSearchResultDto> {
        return Response.success(KnowledgeSearchResultDto())
    }

    override suspend fun getTimeline(limit: Int): Response<TimelineResponseDto> {
        return Response.success(TimelineResponseDto())
    }

    // Phase 10: Personal Assistant APIs. These methods keep this shared
    // AtlasApiService fake complete as the production interface evolves.
    // cancelReminder mirrors ReminderService.cancel(): it returns the same
    // reminder identity with the terminal "cancelled" status.
    override suspend fun createReminder(request: CreateReminderRequest): Response<ReminderDto> {
        return Response.success(
            fakeReminder(
                id = "fake-reminder-1",
                title = request.title,
                dueAt = request.dueAt,
                timezone = request.timezone,
                recurrence = request.recurrence,
                recurrenceDays = request.recurrenceDays,
                status = "pending",
                source = "manual",
                notes = request.notes
            )
        )
    }

    override suspend fun createReminderFromText(request: CreateReminderFromTextRequest): Response<ReminderDto> {
        return Response.success(
            fakeReminder(
                id = "fake-reminder-from-text-1",
                title = request.text,
                rawWhenText = request.text,
                timezone = request.timezone,
                status = "pending",
                source = "text",
                conversationId = request.conversationId
            )
        )
    }

    override suspend fun listReminders(
        status: String?,
        skip: Int,
        limit: Int
    ): Response<List<ReminderDto>> {
        return Response.success(emptyList())
    }

    override suspend fun listUpcomingReminders(withinHours: Int): Response<List<ReminderDto>> {
        return Response.success(emptyList())
    }

    override suspend fun getReminder(reminderId: String): Response<ReminderDto> {
        return Response.success(fakeReminder(id = reminderId))
    }

    override suspend fun completeReminder(reminderId: String): Response<ReminderDto> {
        return Response.success(
            fakeReminder(
                id = reminderId,
                status = "completed",
                completedAt = "fake-completed-at"
            )
        )
    }

    override suspend fun cancelReminder(reminderId: String): Response<ReminderDto> {
        return Response.success(fakeReminder(id = reminderId, status = "cancelled"))
    }

    override suspend fun deleteReminder(reminderId: String): Response<ReminderDto> {
        return Response.success(fakeReminder(id = reminderId))
    }

    override suspend fun createTask(request: CreateTaskRequest): Response<TaskDto> {
        return Response.success(
            TaskDto(
                id = "fake-task-1",
                title = request.title,
                description = request.description,
                status = "pending",
                priority = request.priority,
                dueAt = request.dueAt,
                source = "manual",
                createdAt = "fake-created-at",
                updatedAt = "fake-updated-at"
            )
        )
    }

    override suspend fun listTasks(
        status: String?,
        priority: String?,
        skip: Int,
        limit: Int
    ): Response<List<TaskDto>> {
        return Response.success(emptyList())
    }

    override suspend fun completeTask(taskId: String): Response<TaskDto> {
        return Response.success(fakeTask(id = taskId, status = "completed", completedAt = "fake-completed-at"))
    }

    override suspend fun cancelTask(taskId: String): Response<TaskDto> {
        return Response.success(fakeTask(id = taskId, status = "cancelled"))
    }

    override suspend fun prioritizeTask(taskId: String, request: PrioritizeTaskRequest): Response<TaskDto> {
        return Response.success(fakeTask(id = taskId, priority = request.priority))
    }

    override suspend fun deleteTask(taskId: String): Response<TaskDto> {
        return Response.success(fakeTask(id = taskId))
    }

    override suspend fun createRoutine(request: CreateRoutineRequest): Response<RoutineDto> {
        return Response.success(
            RoutineDto(
                id = "fake-routine-1",
                name = request.name,
                description = request.description,
                steps = request.steps,
                timeOfDay = request.timeOfDay,
                daysOfWeek = request.daysOfWeek,
                isActive = true,
                createdAt = "fake-created-at",
                updatedAt = "fake-updated-at"
            )
        )
    }

    override suspend fun listRoutines(
        isActive: Boolean?,
        skip: Int,
        limit: Int
    ): Response<List<RoutineDto>> {
        return Response.success(emptyList())
    }

    override suspend fun updateRoutine(routineId: String, request: UpdateRoutineRequest): Response<RoutineDto> {
        return Response.success(
            RoutineDto(
                id = routineId,
                name = request.name ?: "Fake routine",
                description = request.description,
                steps = request.steps ?: emptyList(),
                timeOfDay = request.timeOfDay,
                daysOfWeek = request.daysOfWeek ?: emptyList(),
                isActive = request.isActive ?: true,
                createdAt = "fake-created-at",
                updatedAt = "fake-updated-at"
            )
        )
    }

    override suspend fun deleteRoutine(routineId: String): Response<RoutineDto> {
        return Response.success(
            RoutineDto(
                id = routineId,
                name = "Fake routine",
                isActive = false,
                createdAt = "fake-created-at",
                updatedAt = "fake-updated-at"
            )
        )
    }

    override suspend fun getDailyBriefing(withinHours: Int): Response<DailyBriefingDto> {
        return Response.success(DailyBriefingDto(generatedAt = "fake-generated-at"))
    }

    override suspend fun getProactiveSuggestions(): Response<ProactiveSuggestionsDto> {
        return Response.success(
            ProactiveSuggestionsDto(generatedAt = "fake-generated-at")
        )
    }

    private fun fakeReminder(
        id: String,
        title: String = "Fake reminder",
        dueAt: String? = null,
        rawWhenText: String? = null,
        timezone: String = "UTC",
        recurrence: String = "none",
        recurrenceDays: List<Int> = emptyList(),
        status: String = "pending",
        completedAt: String? = null,
        source: String = "manual",
        conversationId: String? = null,
        notes: String? = null
    ): ReminderDto {
        return ReminderDto(
            id = id,
            title = title,
            dueAt = dueAt,
            rawWhenText = rawWhenText,
            timezone = timezone,
            recurrence = recurrence,
            recurrenceDays = recurrenceDays,
            status = status,
            completedAt = completedAt,
            source = source,
            conversationId = conversationId,
            notes = notes,
            createdAt = "fake-created-at",
            updatedAt = "fake-updated-at"
        )
    }

    private fun fakeTask(
        id: String,
        title: String = "Fake task",
        status: String = "pending",
        priority: String = "medium",
        completedAt: String? = null
    ): TaskDto {
        return TaskDto(
            id = id,
            title = title,
            status = status,
            priority = priority,
            completedAt = completedAt,
            source = "manual",
            createdAt = "fake-created-at",
            updatedAt = "fake-updated-at"
        )
    }
}

class ChatRepositoryTest {

    @Test
    fun testCheckHealthSuccess() = runBlocking {
        val fakeApi = FakeAtlasApiService()
        val repository = ChatRepositoryImpl(fakeApi)

        val result = repository.checkHealth()
        assertTrue(result.isSuccess)
        val health = result.getOrNull()
        assertEquals("healthy", health?.status)
        assertEquals("1.0", health?.version)
    }

    @Test
    fun testSendMessageSuccess() = runBlocking {
        val fakeApi = FakeAtlasApiService()
        val repository = ChatRepositoryImpl(fakeApi)

        val result = repository.sendMessage("Hello", null)
        assertTrue(result.isSuccess)
        val response = result.getOrNull()
        assertEquals("ATLAS received: Hello", response?.response)
        assertEquals(1, response?.conversationId)
    }

    @Test
    fun testReportDeviceActionSuccess() = runBlocking {
        val fakeApi = FakeAtlasApiService()
        val repository = ChatRepositoryImpl(fakeApi)

        val result = repository.reportDeviceAction(
            DeviceActionResultRequest(
                conversationId = 1,
                tool = "launch_app",
                action = "launch_app",
                success = true,
                summary = "Opened WhatsApp."
            )
        )

        assertTrue(result.isSuccess)
        val response = result.getOrNull()
        assertEquals("assistant", response?.role)
        assertTrue(response?.content?.contains("Opened WhatsApp.") == true)
    }
}
