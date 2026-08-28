package com.atlas.ui.screens.assistant

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.atlas.data.models.ReminderDto
import com.atlas.data.models.RoutineDto
import com.atlas.data.models.TaskDto

/**
 * Phase 10: Personal Assistant hub - Daily Briefing, Reminders, Tasks,
 * Routines in one screen with tabs, mirroring KnowledgeHubScreen's
 * "one hub, several sub-sections" shape rather than four separate
 * top-level nav destinations for what's really one feature area.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PersonalAssistantScreen(
    viewModel: PersonalAssistantViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Assistant") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(imageVector = Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            TabRow(selectedTabIndex = uiState.selectedTab.ordinal) {
                AssistantTab.values().forEach { tab ->
                    Tab(
                        selected = uiState.selectedTab == tab,
                        onClick = { viewModel.selectTab(tab) },
                        text = { Text(tab.name.lowercase().replaceFirstChar { it.uppercase() }) }
                    )
                }
            }

            uiState.error?.let { errText ->
                Surface(color = MaterialTheme.colorScheme.errorContainer, modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(errText, color = MaterialTheme.colorScheme.onErrorContainer, modifier = Modifier.weight(1f))
                        TextButton(onClick = { viewModel.clearError() }) { Text("Dismiss") }
                    }
                }
            }

            if (uiState.isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }

            when (uiState.selectedTab) {
                AssistantTab.BRIEFING -> BriefingTab(uiState)
                AssistantTab.REMINDERS -> RemindersTab(uiState, viewModel)
                AssistantTab.TASKS -> TasksTab(uiState, viewModel)
                AssistantTab.ROUTINES -> RoutinesTab(uiState, viewModel)
            }
        }
    }
}

@Composable
private fun BriefingTab(uiState: PersonalAssistantUiState) {
    val briefing = uiState.briefing
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = briefing?.narrative ?: if (uiState.isLoading) "Loading..." else "No briefing yet.",
                    modifier = Modifier.padding(16.dp)
                )
            }
        }
        if (briefing != null && briefing.upcomingReminders.isNotEmpty()) {
            item { SectionHeader("Upcoming reminders") }
            items(briefing.upcomingReminders) { reminder -> ReminderRow(reminder, onComplete = null, onCancel = null) }
        }
        if (briefing != null && briefing.incompleteTasks.isNotEmpty()) {
            item { SectionHeader("Incomplete tasks") }
            items(briefing.incompleteTasks) { task -> TaskRow(task, onComplete = null, onCancel = null) }
        }
        if (briefing != null && briefing.routinesToday.isNotEmpty()) {
            item { SectionHeader("Routines around now") }
            items(briefing.routinesToday) { routine -> RoutineRow(routine, onDelete = null) }
        }
    }
}

@Composable
private fun RemindersTab(uiState: PersonalAssistantUiState, viewModel: PersonalAssistantViewModel) {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = uiState.newReminderText,
                onValueChange = { viewModel.onNewReminderTextChanged(it) },
                placeholder = { Text("Remind me to... tomorrow at 7pm") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(onClick = { viewModel.addReminderFromText() }) {
                Icon(imageVector = Icons.Default.Add, contentDescription = "Add reminder")
            }
        }
        if (uiState.remindersLoaded && uiState.reminders.isEmpty()) {
            EmptyState("No pending reminders.")
        } else {
            LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(uiState.reminders, key = { it.id }) { reminder ->
                    ReminderRow(
                        reminder,
                        onComplete = { viewModel.completeReminder(reminder.id) },
                        onCancel = { viewModel.cancelReminder(reminder.id) }
                    )
                }
            }
        }
    }
}

@Composable
private fun TasksTab(uiState: PersonalAssistantUiState, viewModel: PersonalAssistantViewModel) {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = uiState.newTaskTitle,
                onValueChange = { viewModel.onNewTaskTitleChanged(it) },
                placeholder = { Text("Add a task...") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(onClick = { viewModel.addTask() }) {
                Icon(imageVector = Icons.Default.Add, contentDescription = "Add task")
            }
        }
        if (uiState.tasksLoaded && uiState.tasks.isEmpty()) {
            EmptyState("No tasks.")
        } else {
            LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(uiState.tasks, key = { it.id }) { task ->
                    TaskRow(
                        task,
                        onComplete = { viewModel.completeTask(task.id) },
                        onCancel = { viewModel.cancelTask(task.id) }
                    )
                }
            }
        }
    }
}

@Composable
private fun RoutinesTab(uiState: PersonalAssistantUiState, viewModel: PersonalAssistantViewModel) {
    // Phase 10: routine *creation* is deliberately not offered here as a
    // free-text quick-add the way reminders/tasks are - see
    // app/models/routine.py's "explicit only, describable" reasoning;
    // a routine's steps deserve a real multi-field form, not a single
    // text box, so creation stays chat-driven ("create a routine called
    // X with steps: a, b, c" - see RoutineSkill) until a dedicated
    // create-routine form is built (see docs/Phase10_KnownLimitations.md).
    if (uiState.routinesLoaded && uiState.routines.isEmpty()) {
        EmptyState("No routines yet. Try telling ATLAS \"create a routine called Morning Routine with steps: drink water, stretch\".")
    } else {
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(uiState.routines, key = { it.id }) { routine ->
                RoutineRow(routine, onDelete = { viewModel.deleteRoutine(routine.id) })
            }
        }
    }
}

@Composable
private fun SectionHeader(text: String) {
    Text(text, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
}

@Composable
private fun EmptyState(text: String) {
    Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Text(text, textAlign = androidx.compose.ui.text.style.TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ReminderRow(reminder: ReminderDto, onComplete: (() -> Unit)?, onCancel: (() -> Unit)?) {
    Card(shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(reminder.title, fontWeight = FontWeight.Medium)
                val whenText = reminder.dueAt ?: reminder.rawWhenText
                if (whenText != null) {
                    Text(whenText, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (reminder.recurrence != "none") {
                    AssistChip(onClick = {}, label = { Text(reminder.recurrence) })
                }
            }
            if (onComplete != null) {
                IconButton(onClick = onComplete) { Icon(Icons.Default.Check, contentDescription = "Complete") }
            }
            if (onCancel != null) {
                IconButton(onClick = onCancel) { Icon(Icons.Default.Close, contentDescription = "Cancel") }
            }
        }
    }
}

@Composable
private fun TaskRow(task: TaskDto, onComplete: (() -> Unit)?, onCancel: (() -> Unit)?) {
    Card(shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(task.title, fontWeight = FontWeight.Medium)
                AssistChip(onClick = {}, label = { Text(task.priority) })
            }
            if (onComplete != null) {
                IconButton(onClick = onComplete) { Icon(Icons.Default.Check, contentDescription = "Complete") }
            }
            if (onCancel != null) {
                IconButton(onClick = onCancel) { Icon(Icons.Default.Close, contentDescription = "Cancel") }
            }
        }
    }
}

@Composable
private fun RoutineRow(routine: RoutineDto, onDelete: (() -> Unit)?) {
    Card(shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(routine.name, fontWeight = FontWeight.Medium)
                if (routine.steps.isNotEmpty()) {
                    Text(routine.steps.joinToString(" -> "), style = MaterialTheme.typography.bodySmall)
                }
                routine.timeOfDay?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            if (onDelete != null) {
                IconButton(onClick = onDelete) { Icon(Icons.Default.Delete, contentDescription = "Delete") }
            }
        }
    }
}
