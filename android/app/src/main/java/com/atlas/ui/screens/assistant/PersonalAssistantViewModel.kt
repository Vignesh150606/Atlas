package com.atlas.ui.screens.assistant

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.atlas.data.models.CreateReminderFromTextRequest
import com.atlas.data.models.CreateTaskRequest
import com.atlas.data.models.DailyBriefingDto
import com.atlas.data.models.ReminderDto
import com.atlas.data.models.RoutineDto
import com.atlas.data.models.TaskDto
import com.atlas.data.repository.PersonalAssistantRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/** Phase 10: which section of the assistant hub is showing. Reminders,
 * tasks, and routines are loaded lazily (on first tab visit) - only the
 * briefing loads on screen open, since that's the one section meant to
 * be useful at a glance. */
enum class AssistantTab { BRIEFING, REMINDERS, TASKS, ROUTINES }

data class PersonalAssistantUiState(
    val selectedTab: AssistantTab = AssistantTab.BRIEFING,
    val briefing: DailyBriefingDto? = null,
    val reminders: List<ReminderDto> = emptyList(),
    val tasks: List<TaskDto> = emptyList(),
    val routines: List<RoutineDto> = emptyList(),
    val remindersLoaded: Boolean = false,
    val tasksLoaded: Boolean = false,
    val routinesLoaded: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
    val newReminderText: String = "",
    val newTaskTitle: String = ""
)

@HiltViewModel
class PersonalAssistantViewModel @Inject constructor(
    private val repository: PersonalAssistantRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(PersonalAssistantUiState())
    val uiState: StateFlow<PersonalAssistantUiState> = _uiState.asStateFlow()

    init {
        loadBriefing()
    }

    fun selectTab(tab: AssistantTab) {
        _uiState.update { it.copy(selectedTab = tab) }
        when (tab) {
            AssistantTab.BRIEFING -> if (uiState.value.briefing == null) loadBriefing()
            AssistantTab.REMINDERS -> if (!uiState.value.remindersLoaded) loadReminders()
            AssistantTab.TASKS -> if (!uiState.value.tasksLoaded) loadTasks()
            AssistantTab.ROUTINES -> if (!uiState.value.routinesLoaded) loadRoutines()
        }
    }

    fun loadBriefing() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            repository.getDailyBriefing()
                .onSuccess { briefing -> _uiState.update { it.copy(briefing = briefing, isLoading = false) } }
                .onFailure { err -> _uiState.update { it.copy(isLoading = false, error = err.message ?: "Failed to load briefing") } }
        }
    }

    fun loadReminders() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            repository.listReminders(status = "pending")
                .onSuccess { reminders -> _uiState.update { it.copy(reminders = reminders, remindersLoaded = true, isLoading = false) } }
                .onFailure { err -> _uiState.update { it.copy(isLoading = false, error = err.message ?: "Failed to load reminders") } }
        }
    }

    fun loadTasks() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            repository.listTasks()
                .onSuccess { tasks -> _uiState.update { it.copy(tasks = tasks, tasksLoaded = true, isLoading = false) } }
                .onFailure { err -> _uiState.update { it.copy(isLoading = false, error = err.message ?: "Failed to load tasks") } }
        }
    }

    fun loadRoutines() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            repository.listRoutines()
                .onSuccess { routines -> _uiState.update { it.copy(routines = routines, routinesLoaded = true, isLoading = false) } }
                .onFailure { err -> _uiState.update { it.copy(isLoading = false, error = err.message ?: "Failed to load routines") } }
        }
    }

    fun onNewReminderTextChanged(text: String) {
        _uiState.update { it.copy(newReminderText = text) }
    }

    /** Reuses the exact same "remind me to ..." text parsing chat uses -
     * see backend app/api/v1/endpoints/reminders.py::create_reminder_from_text -
     * so a reminder added here interprets "tomorrow at 7pm" identically
     * to one added by talking to ATLAS. */
    fun addReminderFromText() {
        val text = uiState.value.newReminderText.trim()
        if (text.isBlank()) return
        viewModelScope.launch {
            repository.createReminderFromText(CreateReminderFromTextRequest(text = text))
                .onSuccess {
                    _uiState.update { it.copy(newReminderText = "") }
                    loadReminders()
                }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Couldn't create that reminder") } }
        }
    }

    fun completeReminder(id: String) {
        viewModelScope.launch {
            repository.completeReminder(id)
                .onSuccess { updated -> replaceOrRemoveReminder(id, updated.takeIf { it.status == "pending" }) }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Failed to complete reminder") } }
        }
    }

    fun cancelReminder(id: String) {
        viewModelScope.launch {
            repository.cancelReminder(id)
                .onSuccess { _uiState.update { state -> state.copy(reminders = state.reminders.filterNot { it.id == id }) } }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Failed to cancel reminder") } }
        }
    }

    private fun replaceOrRemoveReminder(id: String, stillPending: ReminderDto?) {
        _uiState.update { state ->
            state.copy(reminders = if (stillPending != null) {
                // Recurring reminder: still pending, but due_at advanced - update in place.
                state.reminders.map { if (it.id == id) stillPending else it }
            } else {
                state.reminders.filterNot { it.id == id }
            })
        }
    }

    fun onNewTaskTitleChanged(title: String) {
        _uiState.update { it.copy(newTaskTitle = title) }
    }

    fun addTask() {
        val title = uiState.value.newTaskTitle.trim()
        if (title.isBlank()) return
        viewModelScope.launch {
            repository.createTask(CreateTaskRequest(title = title))
                .onSuccess {
                    _uiState.update { it.copy(newTaskTitle = "") }
                    loadTasks()
                }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Couldn't create that task") } }
        }
    }

    fun completeTask(id: String) {
        viewModelScope.launch {
            repository.completeTask(id)
                .onSuccess { _uiState.update { state -> state.copy(tasks = state.tasks.filterNot { it.id == id }) } }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Failed to complete task") } }
        }
    }

    fun cancelTask(id: String) {
        viewModelScope.launch {
            repository.cancelTask(id)
                .onSuccess { _uiState.update { state -> state.copy(tasks = state.tasks.filterNot { it.id == id }) } }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Failed to cancel task") } }
        }
    }

    fun prioritizeTask(id: String, priority: String) {
        viewModelScope.launch {
            repository.prioritizeTask(id, priority)
                .onSuccess { updated -> _uiState.update { state -> state.copy(tasks = state.tasks.map { if (it.id == id) updated else it }) } }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Failed to update priority") } }
        }
    }

    fun deleteRoutine(id: String) {
        viewModelScope.launch {
            repository.deleteRoutine(id)
                .onSuccess { _uiState.update { state -> state.copy(routines = state.routines.filterNot { it.id == id }) } }
                .onFailure { err -> _uiState.update { it.copy(error = err.message ?: "Failed to delete routine") } }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
