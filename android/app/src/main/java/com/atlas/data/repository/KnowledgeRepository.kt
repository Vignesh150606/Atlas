package com.atlas.data.repository

import com.atlas.api.AtlasApiService
import com.atlas.data.models.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Response
import javax.inject.Inject
import javax.inject.Singleton

interface KnowledgeRepository {
    suspend fun uploadDocument(
        filename: String,
        bytes: ByteArray,
        mimeType: String,
        title: String? = null,
        tags: List<String>? = null,
        author: String? = null
    ): Result<DocumentDto>

    suspend fun listDocuments(
        fileType: String? = null,
        source: String? = null,
        tag: String? = null,
        skip: Int = 0,
        limit: Int = 100
    ): Result<List<DocumentSummaryDto>>

    suspend fun searchDocuments(query: String, fileType: String? = null, limit: Int = 50): Result<List<DocumentSummaryDto>>
    suspend fun getDocument(documentId: String): Result<DocumentDto>
    suspend fun getDocumentEntities(documentId: String): Result<List<EntityDto>>
    suspend fun deleteDocument(documentId: String): Result<DocumentDto>

    suspend fun listEntities(
        entityType: String? = null,
        documentId: String? = null,
        skip: Int = 0,
        limit: Int = 200
    ): Result<List<EntityDto>>

    suspend fun searchKnowledge(query: String, limit: Int = 10): Result<KnowledgeSearchResultDto>
    suspend fun getTimeline(limit: Int = 100): Result<TimelineResponseDto>
}

@Singleton
class KnowledgeRepositoryImpl @Inject constructor(
    private val apiService: AtlasApiService
) : KnowledgeRepository {

    override suspend fun uploadDocument(
        filename: String,
        bytes: ByteArray,
        mimeType: String,
        title: String?,
        tags: List<String>?,
        author: String?
    ): Result<DocumentDto> = safeCall {
        val fileBody = bytes.toRequestBody(mimeType.toMediaTypeOrNull())
        val filePart = MultipartBody.Part.createFormData("file", filename, fileBody)
        val titlePart = title?.toRequestBody("text/plain".toMediaTypeOrNull())
        val tagsPart = tags?.takeIf { it.isNotEmpty() }?.joinToString(",")?.toRequestBody("text/plain".toMediaTypeOrNull())
        val authorPart = author?.toRequestBody("text/plain".toMediaTypeOrNull())
        apiService.uploadDocument(filePart, titlePart, tagsPart, authorPart)
    }

    override suspend fun listDocuments(
        fileType: String?, source: String?, tag: String?, skip: Int, limit: Int
    ): Result<List<DocumentSummaryDto>> = safeCall {
        apiService.listDocuments(fileType = fileType, source = source, tag = tag, skip = skip, limit = limit)
    }

    override suspend fun searchDocuments(query: String, fileType: String?, limit: Int): Result<List<DocumentSummaryDto>> =
        safeCall { apiService.searchDocuments(query = query, fileType = fileType, limit = limit) }

    override suspend fun getDocument(documentId: String): Result<DocumentDto> =
        safeCall { apiService.getDocument(documentId) }

    override suspend fun getDocumentEntities(documentId: String): Result<List<EntityDto>> =
        safeCall { apiService.getDocumentEntities(documentId) }

    override suspend fun deleteDocument(documentId: String): Result<DocumentDto> =
        safeCall { apiService.deleteDocument(documentId) }

    override suspend fun listEntities(
        entityType: String?, documentId: String?, skip: Int, limit: Int
    ): Result<List<EntityDto>> = safeCall {
        apiService.listEntities(entityType = entityType, documentId = documentId, skip = skip, limit = limit)
    }

    override suspend fun searchKnowledge(query: String, limit: Int): Result<KnowledgeSearchResultDto> =
        safeCall { apiService.searchKnowledge(query = query, limit = limit) }

    override suspend fun getTimeline(limit: Int): Result<TimelineResponseDto> =
        safeCall { apiService.getTimeline(limit = limit) }

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
