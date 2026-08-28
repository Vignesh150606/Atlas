package com.atlas.ui.screens.settings

import androidx.lifecycle.ViewModel
import com.atlas.data.local.ApiKeyStore
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import javax.inject.Inject

data class SettingsUiState(
    val apiKey: String = "",
    val savedConfirmation: Boolean = false
)

/**
 * Phase 11: only owns the new API key field for now. Deliberately not a
 * bigger "app settings" ViewModel beyond that - Provider/Backend URL
 * above it in SettingsScreen are still build-time BuildConfig values
 * with no runtime-editable state, unchanged from before this phase.
 */
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val apiKeyStore: ApiKeyStore
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState(apiKey = apiKeyStore.getApiKey() ?: ""))
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    fun onApiKeyChanged(value: String) {
        _uiState.update { it.copy(apiKey = value, savedConfirmation = false) }
    }

    fun saveApiKey() {
        apiKeyStore.setApiKey(_uiState.value.apiKey)
        _uiState.update { it.copy(savedConfirmation = true) }
    }

    /** Only clears the confirmation flag - never touches apiKey, so it's
     * safe to call after a delay even if the user has since started
     * typing a new value (a naive re-set of the whole state using a
     * value captured before the delay would clobber that typing). */
    fun clearSavedConfirmation() {
        _uiState.update { it.copy(savedConfirmation = false) }
    }
}
