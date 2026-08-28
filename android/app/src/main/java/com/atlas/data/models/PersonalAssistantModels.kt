package com.atlas.data.models

import com.google.gson.annotations.SerializedName

/**
 * Phase 10: Personal Assistant & Proactive Intelligence.
 *
 * Mirrors app/schemas/reminder.py, task.py, routine.py, briefing.py on
 * the backend, following exactly the same DTO-per-schema pattern as
 * MemoryModels.kt/KnowledgeModels.kt (see those files for the reasoning:
 * matching backend field names via @SerializedName rather than an
 * automatic converter keeps a drift in either direction visible in one
 * file, not spread across call sites).
 */

// --- Reminders ---------------------------------------------------------
data class ReminderDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("due_at") val dueAt: String? = null,
    @SerializedName("raw_when_text") val rawWhenText: String? = null,
    @SerializedName("timezone") val timezone: String,
    @SerializedName("recurrence") val recurrence: String,
    @SerializedName("recurrence_days") val recurrenceDays: List<Int> = emptyList(),
    @SerializedName("status") val status: String,
    @SerializedName("completed_at") val completedAt: String? = null,
    @SerializedName("source") val source: String,
    @SerializedName("conversation_id") val conversationId: String? = null,
    @SerializedName("notes") val notes: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class CreateReminderRequest(
    @SerializedName("title") val title: String,
    @SerializedName("due_at") val dueAt: String? = null,
    @SerializedName("timezone") val timezone: String = "UTC",
    @SerializedName("recurrence") val recurrence: String = "none",
    @SerializedName("recurrence_days") val recurrenceDays: List<Int> = emptyList(),
    @SerializedName("notes") val notes: String? = null
)

data class CreateReminderFromTextRequest(
    @SerializedName("text") val text: String,
    @SerializedName("timezone") val timezone: String = "UTC",
    @SerializedName("conversation_id") val conversationId: String? = null
)

// --- Tasks ---------------------------------------------------------------
data class TaskDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("description") val description: String? = null,
    @SerializedName("status") val status: String,
    @SerializedName("priority") val priority: String,
    @SerializedName("due_at") val dueAt: String? = null,
    @SerializedName("completed_at") val completedAt: String? = null,
    @SerializedName("source") val source: String,
    @SerializedName("conversation_id") val conversationId: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class CreateTaskRequest(
    @SerializedName("title") val title: String,
    @SerializedName("description") val description: String? = null,
    @SerializedName("priority") val priority: String = "medium",
    @SerializedName("due_at") val dueAt: String? = null
)

data class PrioritizeTaskRequest(
    @SerializedName("priority") val priority: String
)

// --- Routines --------------------------------------------------------------
data class RoutineDto(
    @SerializedName("id") val id: String,
    @SerializedName("name") val name: String,
    @SerializedName("description") val description: String? = null,
    @SerializedName("steps") val steps: List<String> = emptyList(),
    @SerializedName("time_of_day") val timeOfDay: String? = null,
    @SerializedName("days_of_week") val daysOfWeek: List<Int> = emptyList(),
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class CreateRoutineRequest(
    @SerializedName("name") val name: String,
    @SerializedName("description") val description: String? = null,
    @SerializedName("steps") val steps: List<String> = emptyList(),
    @SerializedName("time_of_day") val timeOfDay: String? = null,
    @SerializedName("days_of_week") val daysOfWeek: List<Int> = emptyList()
)

data class UpdateRoutineRequest(
    @SerializedName("name") val name: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("steps") val steps: List<String>? = null,
    @SerializedName("time_of_day") val timeOfDay: String? = null,
    @SerializedName("days_of_week") val daysOfWeek: List<Int>? = null,
    @SerializedName("is_active") val isActive: Boolean? = null
)

// --- Daily Briefing / Proactive Suggestions -----------------------------
data class BriefingMemoryItemDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("category") val category: String,
    @SerializedName("importance") val importance: Int
)

data class DailyBriefingDto(
    @SerializedName("generated_at") val generatedAt: String,
    @SerializedName("upcoming_reminders") val upcomingReminders: List<ReminderDto> = emptyList(),
    @SerializedName("incomplete_tasks") val incompleteTasks: List<TaskDto> = emptyList(),
    @SerializedName("routines_today") val routinesToday: List<RoutineDto> = emptyList(),
    @SerializedName("important_memories") val importantMemories: List<BriefingMemoryItemDto> = emptyList(),
    @SerializedName("stale_memory_count") val staleMemoryCount: Int = 0,
    @SerializedName("narrative") val narrative: String = ""
)

/**
 * Mirrors backend app/schemas/briefing.py::ProactiveSuggestion.
 * `suggestionType` is a small closed set (see backend docstring) - render
 * by type, don't string-match `message`.
 */
data class ProactiveSuggestionDto(
    @SerializedName("suggestion_type") val suggestionType: String,
    @SerializedName("message") val message: String,
    @SerializedName("related_id") val relatedId: String? = null,
    @SerializedName("related_type") val relatedType: String? = null
)

data class ProactiveSuggestionsDto(
    @SerializedName("generated_at") val generatedAt: String,
    @SerializedName("suggestions") val suggestions: List<ProactiveSuggestionDto> = emptyList()
)
