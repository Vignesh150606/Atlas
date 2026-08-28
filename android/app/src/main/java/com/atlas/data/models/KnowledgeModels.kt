package com.atlas.data.models

import com.google.gson.annotations.SerializedName

enum class DocumentTypeEnum(val value: String) {
    PDF("pdf"),
    MARKDOWN("markdown"),
    TXT("txt"),
    JSON("json"),
    CSV("csv")
}

enum class EntityTypeEnum(val value: String) {
    PERSON("person"),
    PROJECT("project"),
    COMPANY("company"),
    COURSE("course"),
    TOPIC("topic"),
    TASK("task"),
    DEADLINE("deadline"),
    SKILL("skill")
}

data class DocumentDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("source") val source: String,
    @SerializedName("file_type") val fileType: String,
    @SerializedName("original_filename") val originalFilename: String? = null,
    @SerializedName("author") val author: String? = null,
    @SerializedName("tags") val tags: List<String> = emptyList(),
    @SerializedName("content") val content: String = "",
    @SerializedName("structured_data") val structuredData: Map<String, Any> = emptyMap(),
    @SerializedName("content_hash") val contentHash: String? = null,
    @SerializedName("size_bytes") val sizeBytes: Int = 0,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("updated_at") val updatedAt: String? = null,
    @SerializedName("deleted_at") val deletedAt: String? = null
)

data class DocumentSummaryDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("source") val source: String,
    @SerializedName("file_type") val fileType: String,
    @SerializedName("tags") val tags: List<String> = emptyList(),
    @SerializedName("author") val author: String? = null,
    @SerializedName("size_bytes") val sizeBytes: Int = 0,
    @SerializedName("created_at") val createdAt: String? = null
)

data class DocumentUpdateRequest(
    @SerializedName("title") val title: String? = null,
    @SerializedName("tags") val tags: List<String>? = null,
    @SerializedName("author") val author: String? = null
)

data class EntityDto(
    @SerializedName("id") val id: Int,
    @SerializedName("entity_type") val entityType: String,
    @SerializedName("name") val name: String,
    @SerializedName("details") val details: Map<String, Any> = emptyMap(),
    @SerializedName("document_id") val documentId: String,
    @SerializedName("confidence") val confidence: Int = 0,
    @SerializedName("created_at") val createdAt: String? = null
)

data class DocumentSnippetDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("file_type") val fileType: String,
    @SerializedName("snippet") val snippet: String = ""
)

data class EntitySnippetDto(
    @SerializedName("id") val id: Int,
    @SerializedName("entity_type") val entityType: String,
    @SerializedName("name") val name: String,
    @SerializedName("document_id") val documentId: String
)

data class KnowledgeSearchResultDto(
    @SerializedName("documents") val documents: List<DocumentSnippetDto> = emptyList(),
    @SerializedName("entities") val entities: List<EntitySnippetDto> = emptyList()
)

data class TimelineItemDto(
    @SerializedName("entity_id") val entityId: Int,
    @SerializedName("entity_type") val entityType: String,
    @SerializedName("name") val name: String,
    @SerializedName("document_id") val documentId: String,
    @SerializedName("date") val date: String? = null
)

data class TimelineResponseDto(
    @SerializedName("dated") val dated: List<TimelineItemDto> = emptyList(),
    @SerializedName("undated") val undated: List<TimelineItemDto> = emptyList()
)
