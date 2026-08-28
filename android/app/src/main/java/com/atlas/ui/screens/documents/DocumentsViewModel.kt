package com.atlas.ui.screens.documents

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.atlas.data.models.DocumentSummaryDto
import com.atlas.data.repository.KnowledgeRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DocumentsUiState(
    val documents: List<DocumentSummaryDto> = emptyList(),
    val isLoading: Boolean = false,
    val isUploading: Boolean = false,
    val error: String? = null,
    val searchQuery: String = "",
    val selectedFileType: String? = null
)

@HiltViewModel
class DocumentsViewModel @Inject constructor(
    private val repository: KnowledgeRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(DocumentsUiState())
    val uiState: StateFlow<DocumentsUiState> = _uiState.asStateFlow()

    private var searchDebounceJob: Job? = null

    init {
        loadDocuments()
    }

    fun loadDocuments() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            val query = uiState.value.searchQuery.trim()
            val fileType = uiState.value.selectedFileType

            val result = if (query.isNotEmpty()) {
                repository.searchDocuments(query = query, fileType = fileType)
            } else {
                repository.listDocuments(fileType = fileType, limit = 200)
            }

            result
                .onSuccess { docs -> _uiState.update { it.copy(documents = docs, isLoading = false) } }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, error = err.message ?: "Failed to load documents") }
                }
        }
    }

    fun onSearchQueryChanged(query: String) {
        _uiState.update { it.copy(searchQuery = query) }
        searchDebounceJob?.cancel()
        searchDebounceJob = viewModelScope.launch {
            delay(350)
            loadDocuments()
        }
    }

    fun onFileTypeSelected(fileType: String?) {
        if (uiState.value.selectedFileType == fileType) return
        _uiState.update { it.copy(selectedFileType = fileType) }
        loadDocuments()
    }

    fun uploadDocument(filename: String, bytes: ByteArray, mimeType: String) {
        _uiState.update { it.copy(isUploading = true, error = null) }
        viewModelScope.launch {
            repository.uploadDocument(filename = filename, bytes = bytes, mimeType = mimeType)
                .onSuccess {
                    _uiState.update { it.copy(isUploading = false) }
                    loadDocuments()
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isUploading = false, error = err.message ?: "Upload failed") }
                }
        }
    }

    fun deleteDocument(documentId: String) {
        viewModelScope.launch {
            repository.deleteDocument(documentId)
                .onSuccess {
                    _uiState.update { state ->
                        state.copy(documents = state.documents.filterNot { it.id == documentId })
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(error = err.message ?: "Failed to delete document") }
                }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
