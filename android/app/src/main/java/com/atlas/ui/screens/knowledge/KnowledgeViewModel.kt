package com.atlas.ui.screens.knowledge

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.atlas.data.models.EntityDto
import com.atlas.data.models.EntityTypeEnum
import com.atlas.data.repository.KnowledgeRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class KnowledgeUiState(
    val entities: List<EntityDto> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val selectedType: EntityTypeEnum? = null
)

@HiltViewModel
class KnowledgeViewModel @Inject constructor(
    private val repository: KnowledgeRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(KnowledgeUiState())
    val uiState: StateFlow<KnowledgeUiState> = _uiState.asStateFlow()

    init {
        loadEntities()
    }

    fun loadEntities() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            repository.listEntities(entityType = uiState.value.selectedType?.value, limit = 300)
                .onSuccess { entities -> _uiState.update { it.copy(entities = entities, isLoading = false) } }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, error = err.message ?: "Failed to load knowledge") }
                }
        }
    }

    fun onTypeSelected(type: EntityTypeEnum?) {
        if (uiState.value.selectedType == type) return
        _uiState.update { it.copy(selectedType = type) }
        loadEntities()
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
