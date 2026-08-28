package com.atlas.ui.screens.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.atlas.data.models.DocumentSnippetDto
import com.atlas.data.models.EntitySnippetDto
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

data class SearchUiState(
    val query: String = "",
    val documents: List<DocumentSnippetDto> = emptyList(),
    val entities: List<EntitySnippetDto> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val hasSearched: Boolean = false
)

@HiltViewModel
class SearchViewModel @Inject constructor(
    private val repository: KnowledgeRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(SearchUiState())
    val uiState: StateFlow<SearchUiState> = _uiState.asStateFlow()

    private var searchDebounceJob: Job? = null

    fun onQueryChanged(query: String) {
        _uiState.update { it.copy(query = query) }
        searchDebounceJob?.cancel()
        if (query.isBlank()) {
            _uiState.update { it.copy(documents = emptyList(), entities = emptyList(), hasSearched = false) }
            return
        }
        searchDebounceJob = viewModelScope.launch {
            delay(350)
            search()
        }
    }

    private fun search() {
        val query = uiState.value.query.trim()
        if (query.isEmpty()) return

        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            repository.searchKnowledge(query = query)
                .onSuccess { result ->
                    _uiState.update {
                        it.copy(
                            documents = result.documents,
                            entities = result.entities,
                            isLoading = false,
                            hasSearched = true,
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, error = err.message ?: "Search failed") }
                }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
