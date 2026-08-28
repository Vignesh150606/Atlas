package com.atlas.ui.screens.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.atlas.data.models.MemoryDto
import com.atlas.data.models.MemoryTypeEnum
import com.atlas.data.models.UpdateMemoryRequest
import com.atlas.data.repository.MemoryRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MemoryUiState(
    val memories: List<MemoryDto> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val searchQuery: String = "",
    val selectedType: MemoryTypeEnum? = null
)

@HiltViewModel
class MemoryViewModel @Inject constructor(
    private val repository: MemoryRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(MemoryUiState())
    val uiState: StateFlow<MemoryUiState> = _uiState.asStateFlow()

    private var searchDebounceJob: Job? = null

    init {
        loadMemories()
    }

    fun loadMemories() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            val typeFilter = uiState.value.selectedType?.value
            val query = uiState.value.searchQuery.trim()

            val result = if (query.isNotEmpty()) {
                repository.searchMemories(query = query, memoryType = typeFilter)
            } else {
                repository.listMemories(memoryType = typeFilter, limit = 200)
            }

            result
                .onSuccess { memories ->
                    _uiState.update { it.copy(memories = memories, isLoading = false) }
                }
                .onFailure { err ->
                    _uiState.update {
                        it.copy(isLoading = false, error = err.message ?: "Failed to load memories")
                    }
                }
        }
    }

    /** Debounced so we don't fire a request on every keystroke. */
    fun onSearchQueryChanged(query: String) {
        _uiState.update { it.copy(searchQuery = query) }
        searchDebounceJob?.cancel()
        searchDebounceJob = viewModelScope.launch {
            delay(350)
            loadMemories()
        }
    }

    fun onTypeFilterSelected(type: MemoryTypeEnum?) {
        if (uiState.value.selectedType == type) return
        _uiState.update { it.copy(selectedType = type) }
        loadMemories()
    }

    fun togglePinned(memory: MemoryDto) {
        viewModelScope.launch {
            repository.updateMemory(memory.id, UpdateMemoryRequest(isPinned = !memory.isPinned))
                .onSuccess { updated ->
                    _uiState.update { state ->
                        state.copy(memories = state.memories.map { if (it.id == updated.id) updated else it })
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(error = err.message ?: "Failed to update memory") }
                }
        }
    }

    fun deleteMemory(memoryId: String) {
        viewModelScope.launch {
            repository.deleteMemory(memoryId)
                .onSuccess {
                    _uiState.update { state ->
                        state.copy(memories = state.memories.filterNot { it.id == memoryId })
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(error = err.message ?: "Failed to delete memory") }
                }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
