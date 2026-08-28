package com.atlas.data.repository

import com.atlas.api.AtlasApiService
import com.atlas.data.models.*
import retrofit2.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 10: Personal Assistant & Proactive Intelligence. Same
 * repository-interface-plus-Impl pattern as MemoryRepository/
 * KnowledgeRepository - one repository covering all four Phase 10
 * resources (reminders, tasks, routines, briefing/suggestions) rather
 * than four separate repository files, since they're small, share the
 * same safeCall plumbing, and are typically consumed together by the
 * same screens (see ui/screens/assistant/).
 */
interface PersonalAssistantRepository {
    // Reminders
    suspend fun createReminder(request: CreateReminderRequest): Result<ReminderDto>
    suspend fun createReminderFromText(request: CreateReminderFromTextRequest): Result<ReminderDto>
    suspend fun listReminders(status: String? = null, skip: Int = 0, limit: Int = 100): Result<List<ReminderDto>>
    suspend fun listUpcomingReminders(withinHours: Int = 24): Result<List<ReminderDto>>
    suspend fun completeReminder(reminderId: String): Result<ReminderDto>
    suspend fun cancelReminder(reminderId: String): Result<ReminderDto>
    suspend fun deleteReminder(reminderId: String): Result<ReminderDto>

    // Tasks
    suspend fun createTask(request: CreateTaskRequest): Result<TaskDto>
    suspend fun listTasks(status: String? = null, priority: String? = null, skip: Int = 0, limit: Int = 100): Result<List<TaskDto>>
    suspend fun completeTask(taskId: String): Result<TaskDto>
    suspend fun cancelTask(taskId: String): Result<TaskDto>
    suspend fun prioritizeTask(taskId: String, priority: String): Result<TaskDto>
    suspend fun deleteTask(taskId: String): Result<TaskDto>

    // Routines
    suspend fun createRoutine(request: CreateRoutineRequest): Result<RoutineDto>
    suspend fun listRoutines(isActive: Boolean? = null): Result<List<RoutineDto>>
    suspend fun updateRoutine(routineId: String, request: UpdateRoutineRequest): Result<RoutineDto>
    suspend fun deleteRoutine(routineId: String): Result<RoutineDto>

    // Daily briefing + proactive suggestions
    suspend fun getDailyBriefing(withinHours: Int = 24): Result<DailyBriefingDto>
    suspend fun getProactiveSuggestions(): Result<ProactiveSuggestionsDto>
}

@Singleton
class PersonalAssistantRepositoryImpl @Inject constructor(
    private val apiService: AtlasApiService
) : PersonalAssistantRepository {

    override suspend fun createReminder(request: CreateReminderRequest): Result<ReminderDto> = safeCall {
        apiService.createReminder(request)
    }

    override suspend fun createReminderFromText(request: CreateReminderFromTextRequest): Result<ReminderDto> = safeCall {
        apiService.createReminderFromText(request)
    }

    override suspend fun listReminders(status: String?, skip: Int, limit: Int): Result<List<ReminderDto>> = safeCall {
        apiService.listReminders(status = status, skip = skip, limit = limit)
    }

    override suspend fun listUpcomingReminders(withinHours: Int): Result<List<ReminderDto>> = safeCall {
        apiService.listUpcomingReminders(withinHours)
    }

    override suspend fun completeReminder(reminderId: String): Result<ReminderDto> = safeCall {
        apiService.completeReminder(reminderId)
    }

    override suspend fun cancelReminder(reminderId: String): Result<ReminderDto> = safeCall {
        apiService.cancelReminder(reminderId)
    }

    override suspend fun deleteReminder(reminderId: String): Result<ReminderDto> = safeCall {
        apiService.deleteReminder(reminderId)
    }

    override suspend fun createTask(request: CreateTaskRequest): Result<TaskDto> = safeCall {
        apiService.createTask(request)
    }

    override suspend fun listTasks(status: String?, priority: String?, skip: Int, limit: Int): Result<List<TaskDto>> = safeCall {
        apiService.listTasks(status = status, priority = priority, skip = skip, limit = limit)
    }

    override suspend fun completeTask(taskId: String): Result<TaskDto> = safeCall {
        apiService.completeTask(taskId)
    }

    override suspend fun cancelTask(taskId: String): Result<TaskDto> = safeCall {
        apiService.cancelTask(taskId)
    }

    override suspend fun prioritizeTask(taskId: String, priority: String): Result<TaskDto> = safeCall {
        apiService.prioritizeTask(taskId, PrioritizeTaskRequest(priority))
    }

    override suspend fun deleteTask(taskId: String): Result<TaskDto> = safeCall {
        apiService.deleteTask(taskId)
    }

    override suspend fun createRoutine(request: CreateRoutineRequest): Result<RoutineDto> = safeCall {
        apiService.createRoutine(request)
    }

    override suspend fun listRoutines(isActive: Boolean?): Result<List<RoutineDto>> = safeCall {
        apiService.listRoutines(isActive = isActive)
    }

    override suspend fun updateRoutine(routineId: String, request: UpdateRoutineRequest): Result<RoutineDto> = safeCall {
        apiService.updateRoutine(routineId, request)
    }

    override suspend fun deleteRoutine(routineId: String): Result<RoutineDto> = safeCall {
        apiService.deleteRoutine(routineId)
    }

    override suspend fun getDailyBriefing(withinHours: Int): Result<DailyBriefingDto> = safeCall {
        apiService.getDailyBriefing(withinHours)
    }

    override suspend fun getProactiveSuggestions(): Result<ProactiveSuggestionsDto> = safeCall {
        apiService.getProactiveSuggestions()
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
