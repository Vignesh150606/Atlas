package com.atlas.data.models

import com.google.gson.annotations.SerializedName

enum class MemoryTypeEnum(val value: String) {
    FACT("fact"),
    PREFERENCE("preference"),
    TASK("task"),
    EVENT("event"),
    CLASS("class"),
    TIMETABLE("timetable"),
    NOTE("note"),
    PROJECT("project"),
    DOCUMENT("document"),
    CONVERSATION("conversation"),
    CONTACT("contact"),
    GOAL("goal")
}

data class MemoryDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("content") val content: String,
    @SerializedName("memory_type") val memoryType: String,
    @SerializedName("category") val category: String,
    @SerializedName("importance") val importance: Int,
    @SerializedName("is_pinned") val isPinned: Boolean,
    @SerializedName("source") val source: String,
    @SerializedName("tags") val tags: List<String> = emptyList(),
    @SerializedName("structured_data") val structuredData: Map<String, Any> = emptyMap(),
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("updated_at") val updatedAt: String? = null,
    @SerializedName("deleted_at") val deletedAt: String? = null
)

data class CreateMemoryRequest(
    @SerializedName("title") val title: String,
    @SerializedName("content") val content: String,
    @SerializedName("memory_type") val memoryType: String = MemoryTypeEnum.FACT.value,
    @SerializedName("category") val category: String = "general",
    @SerializedName("importance") val importance: Int = 3,
    @SerializedName("is_pinned") val isPinned: Boolean = false,
    @SerializedName("source") val source: String = "manual",
    @SerializedName("tags") val tags: List<String> = emptyList(),
    @SerializedName("structured_data") val structuredData: Map<String, Any> = emptyMap()
)

data class UpdateMemoryRequest(
    @SerializedName("title") val title: String? = null,
    @SerializedName("content") val content: String? = null,
    @SerializedName("memory_type") val memoryType: String? = null,
    @SerializedName("category") val category: String? = null,
    @SerializedName("importance") val importance: Int? = null,
    @SerializedName("is_pinned") val isPinned: Boolean? = null,
    @SerializedName("tags") val tags: List<String>? = null
)
