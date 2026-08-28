package com.atlas.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.atlas.api.AtlasApiService
import com.atlas.data.local.ApiKeyStore
import com.atlas.data.local.ServerConfigStore
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class ConnectionTestResult { NONE, TESTING, SUCCESS, FAILURE }

data class SettingsUiState(
    val apiKey: String = "",
    val savedConfirmation: Boolean = false,
    val baseUrl: String = "",
    val baseUrlIsDefault: Boolean = true,
    val baseUrlSavedConfirmation: Boolean = false,
    val connectionTestResult: ConnectionTestResult = ConnectionTestResult.NONE,
    val connectionTestMessage: String = "",
)

/**
 * Phase 12 (docs/MASTER_PLAN.md #2.1): gained the server URL field - the
 * fix for the audit's CRITICAL finding (a hardcoded, unreachable LAN IP
 * baked into the build). Editing and saving here takes effect on the
 * very next request via BaseUrlInterceptor - no rebuild.
 */
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val apiKeyStore: ApiKeyStore,
    private val serverConfigStore: ServerConfigStore,
    private val apiService: AtlasApiService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        SettingsUiState(
            apiKey = apiKeyStore.getApiKey() ?: "",
            baseUrl = serverConfigStore.getBaseUrl(),
            baseUrlIsDefault = !serverConfigStore.hasExplicitBaseUrl(),
        )
    )
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

    fun onBaseUrlChanged(value: String) {
        _uiState.update {
            it.copy(baseUrlSavedConfirmation = false, connectionTestResult = ConnectionTestResult.NONE, baseUrl = value)
        }
    }

    fun saveBaseUrl() {
        val trimmed = _uiState.value.baseUrl.trim()
        serverConfigStore.setBaseUrl(trimmed)
        _uiState.update {
            it.copy(
                baseUrl = serverConfigStore.getBaseUrl(),
                baseUrlIsDefault = !serverConfigStore.hasExplicitBaseUrl(),
                baseUrlSavedConfirmation = true,
            )
        }
    }

    fun resetBaseUrlToDefault() {
        serverConfigStore.setBaseUrl(null)
        _uiState.update {
            it.copy(
                baseUrl = serverConfigStore.getBaseUrl(),
                baseUrlIsDefault = true,
                baseUrlSavedConfirmation = true,
            )
        }
    }

    fun clearBaseUrlSavedConfirmation() {
        _uiState.update { it.copy(baseUrlSavedConfirmation = false) }
    }

    /** Hits /health with whatever is currently saved (the field must be
     * saved first - this deliberately tests the stored value, not the
     * text field's live, possibly-unsaved contents, so what gets tested
     * is exactly what real requests will use). */
    fun testConnection() {
        _uiState.update { it.copy(connectionTestResult = ConnectionTestResult.TESTING) }
        viewModelScope.launch {
            val result = runCatching { apiService.checkHealth() }
            val outcome = result.getOrNull()
            _uiState.update {
                it.copy(
                    connectionTestResult = if (outcome?.isSuccessful == true) ConnectionTestResult.SUCCESS else ConnectionTestResult.FAILURE,
                    connectionTestMessage = when {
                        outcome?.isSuccessful == true -> "Connected - ${outcome.body()?.status ?: "healthy"}"
                        outcome != null -> "Server responded with an error (HTTP ${outcome.code()})"
                        else -> "Could not reach the server: ${result.exceptionOrNull()?.message ?: "unknown error"}"
                    },
                )
            }
        }
    }
}
