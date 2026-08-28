package com.atlas.ui.screens.permissions

import android.Manifest
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver

/**
 * Phase 8: Android Automation Foundation - Permission Center.
 *
 * Single screen showing every automation permission's live status, an
 * enable action, and a short explanation of what it unlocks - per the
 * mission brief: "Single screen showing Accessibility, Notification
 * Listener, Microphone, Overlay (future), Status, Enable buttons,
 * Documentation."
 *
 * None of Accessibility/Notification Listener can be requested with a
 * single in-app permission dialog the way Microphone can - both require
 * sending the user to a dedicated system Settings screen and trusting them
 * to come back, which is why every row's status is re-read on ON_RESUME
 * (see the DisposableEffect below) rather than cached from when the screen
 * first opened.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PermissionCenterScreen(
    viewModel: PermissionCenterViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    // Re-check every permission's real status whenever this screen becomes
    // visible again - covers both "user tapped Enable, went to system
    // Settings, came back" and "user granted/revoked something from
    // outside the app entirely (e.g. a device Settings shortcut)".
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.refresh()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted -> viewModel.onMicrophonePermissionResult(granted) }

    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted -> viewModel.onNotificationPermissionResult(granted) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Permission Center") },
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
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "ATLAS only acts on requests you make by voice or text - nothing here taps, types, or automates anything on its own. The one exception is Proactive Suggestions below: a periodic background check (roughly every 30 minutes) against reminders, tasks, and routines you already created, which can post a notification - it never takes any action by itself.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            PermissionRow(
                title = "Proactive Suggestions",
                description = "Lets ATLAS notify you about things it already knows about without you having to ask - an overdue reminder, a routine that's about to start. Checked periodically in the background (see Settings > Automation); this permission only controls whether it can show a notification, not whether the check itself runs.",
                enabled = uiState.notificationsGranted,
                actionLabel = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) "Grant Notification Access" else null,
                onAction = {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                }
            )

            PermissionRow(
                title = "Accessibility",
                description = "Lets ATLAS read what's on screen and act on it: tapping, scrolling, typing into fields, and navigating back/home/recents. Required for on-screen automation and for foreground-app detection.",
                enabled = uiState.accessibilityEnabled,
                actionLabel = "Open Accessibility Settings",
                onAction = {
                    context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                }
            )

            PermissionRow(
                title = "Notification Listener",
                description = "Lets ATLAS read your current notifications when you ask about them, and is also what the platform requires for media playback control (play/pause/skip/volume). Read-only: ATLAS never dismisses or replies to notifications on its own.",
                enabled = uiState.notificationListenerEnabled,
                actionLabel = "Open Notification Access Settings",
                onAction = {
                    context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                }
            )

            PermissionRow(
                title = "Microphone",
                description = "Required for Voice mode - speech recognition can't run without it. If tapping this does nothing, Android has permanently denied the prompt; enable it from this app's system Settings page instead.",
                enabled = uiState.microphoneGranted,
                actionLabel = "Grant Microphone Access",
                onAction = {
                    micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                }
            )

            PermissionRow(
                title = "Overlay",
                description = "Coming soon - will let ATLAS draw on-screen highlights while it's working. Not required for anything available today.",
                enabled = false,
                actionLabel = null,
                onAction = {},
                comingSoon = true
            )
        }
    }
}

@Composable
private fun PermissionRow(
    title: String,
    description: String,
    enabled: Boolean,
    actionLabel: String?,
    onAction: () -> Unit,
    comingSoon: Boolean = false
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(text = title, style = MaterialTheme.typography.titleMedium)
                StatusBadge(enabled = enabled, comingSoon = comingSoon)
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text(text = description, style = MaterialTheme.typography.bodySmall)

            if (!comingSoon && actionLabel != null && !enabled) {
                Spacer(modifier = Modifier.height(12.dp))
                Button(onClick = onAction) {
                    Text(actionLabel)
                }
            }
        }
    }
}

@Composable
private fun StatusBadge(enabled: Boolean, comingSoon: Boolean) {
    when {
        comingSoon -> Text(
            text = "Coming soon",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        enabled -> Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = null,
                tint = Color(0xFF2E7D32),
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(4.dp))
            Text(text = "Enabled", style = MaterialTheme.typography.labelMedium, color = Color(0xFF2E7D32))
        }
        else -> Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.error,
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(4.dp))
            Text(text = "Disabled", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.error)
        }
    }
}
