package com.atlas.ui.screens.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onNavigateBack: () -> Unit,
    onNavigateToPermissions: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(imageVector = Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)
        ) {
            Text(text = "Provider", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(4.dp))
            Text(text = "Current Provider: Mock (Phase 1)", style = MaterialTheme.typography.bodyMedium)

            Spacer(modifier = Modifier.height(24.dp))
            Text(text = "Backend Server", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = if (uiState.baseUrlIsDefault) {
                    "Default - only reachable from the Android Emulator, not a physical device or mobile data."
                } else {
                    "Custom server address."
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = uiState.baseUrl,
                onValueChange = viewModel::onBaseUrlChanged,
                label = { Text("Server URL") },
                placeholder = { Text("https://your-server.example.com") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Button(onClick = viewModel::saveBaseUrl) {
                    Text("Save")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(onClick = viewModel::testConnection) {
                    Text("Test Connection")
                }
                if (uiState.baseUrlSavedConfirmation) {
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "Saved",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
            when (uiState.connectionTestResult) {
                ConnectionTestResult.TESTING -> {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Testing...", style = MaterialTheme.typography.bodySmall)
                }
                ConnectionTestResult.SUCCESS -> {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        uiState.connectionTestMessage,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                ConnectionTestResult.FAILURE -> {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        uiState.connectionTestMessage,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
                ConnectionTestResult.NONE -> {}
            }
            LaunchedEffect(uiState.baseUrlSavedConfirmation) {
                if (uiState.baseUrlSavedConfirmation) {
                    kotlinx.coroutines.delay(2000)
                    viewModel.clearBaseUrlSavedConfirmation()
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
            // Phase 11: shared API key (see backend Settings.API_KEY /
            // app/core/deps.py::verify_api_key). Optional - leaving this
            // blank matches a backend with no API_KEY configured, i.e.
            // today's default, unauthenticated behavior.
            Text(text = "API Key", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "Only needed if the backend has API_KEY set. Sent as the X-API-Key header on every request.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = uiState.apiKey,
                onValueChange = viewModel::onApiKeyChanged,
                label = { Text("API Key") },
                placeholder = { Text("Leave blank if the backend has none configured") },
                visualTransformation = PasswordVisualTransformation(),
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Button(onClick = viewModel::saveApiKey) {
                    Text("Save")
                }
                if (uiState.savedConfirmation) {
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "Saved",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
            // Clears the "Saved" confirmation shortly after showing it
            // rather than leaving it stuck indefinitely.
            LaunchedEffect(uiState.savedConfirmation) {
                if (uiState.savedConfirmation) {
                    kotlinx.coroutines.delay(2000)
                    viewModel.clearSavedConfirmation()
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
            Text(text = "Automation", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(4.dp))
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable(onClick = onNavigateToPermissions)
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(text = "Permission Center", style = MaterialTheme.typography.bodyLarge)
                        Text(
                            text = "Accessibility, Notification Listener, Microphone",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Icon(imageVector = Icons.Default.KeyboardArrowRight, contentDescription = null)
                }
            }
        }
    }
}
