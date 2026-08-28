package com.atlas.ui.screens.voice

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.atlas.ui.components.ConfirmationDialog
import com.atlas.ui.components.VoiceOrb
import com.atlas.voice.AudioOutputRoute
import com.atlas.voice.VoiceState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceScreen(
    viewModel: VoiceViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    var hasMicPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted -> hasMicPermission = granted }

    // Phase 10 (mission brief section 9): "Never bypass confirmation
    // merely because the user is using voice" - same dialog ChatScreen
    // uses. ATLAS also speaks a heads-up (see ConversationAudioController)
    // but execution only happens after a tap here.
    uiState.pendingConfirmation?.let { action ->
        ConfirmationDialog(
            action = action,
            onConfirm = { viewModel.confirmPendingDeviceAction() },
            onCancel = { viewModel.cancelPendingDeviceAction() }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Voice") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(imageVector = Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    Text(
                        text = if (uiState.continuousMode) "Continuous" else "Push-to-talk",
                        style = MaterialTheme.typography.labelSmall,
                        modifier = Modifier.padding(end = 4.dp)
                    )
                    Switch(
                        checked = uiState.continuousMode,
                        onCheckedChange = { viewModel.setContinuousMode(it) }
                    )
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            when {
                !hasMicPermission -> {
                    Text(
                        text = "ATLAS needs microphone access to hear you.",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(bottom = 16.dp)
                    )
                    Button(onClick = { permissionLauncher.launch(Manifest.permission.RECORD_AUDIO) }) {
                        Text("Grant microphone access")
                    }
                }
                !viewModel.isMicAvailable() -> {
                    Text(
                        text = "Speech recognition isn't available on this device.",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
                else -> {
                    VoiceOrb(
                        state = uiState.voiceState,
                        amplitude = uiState.amplitude,
                        modifier = Modifier.clickable { handleOrbTap(uiState.voiceState, viewModel) }
                    )

                    Spacer(modifier = Modifier.height(24.dp))

                    Text(
                        text = stateLabel(uiState.voiceState),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )

                    // Phase 8 stabilization: VoiceSessionState.outputRoute was
                    // already being tracked correctly (refreshed on every
                    // startListening() call - see ConversationAudioController)
                    // but was never actually rendered anywhere, so there was
                    // no way to visually verify Bluetooth/wired-headset
                    // routing was being detected. Kept intentionally small
                    // and unobtrusive - it's a diagnostic signal, not a
                    // primary control.
                    Text(
                        text = outputRouteLabel(uiState.outputRoute),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    val transcriptToShow = when {
                        uiState.partialTranscript.isNotBlank() -> uiState.partialTranscript
                        uiState.voiceState == VoiceState.SPEAKING || uiState.voiceState == VoiceState.PROCESSING -> uiState.lastResponse
                        uiState.transcript.isNotBlank() -> uiState.transcript
                        else -> "Tap the orb to talk"
                    }
                    Text(
                        text = transcriptToShow,
                        style = MaterialTheme.typography.bodyLarge,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 16.dp)
                    )

                    Spacer(modifier = Modifier.height(24.dp))

                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        if (uiState.voiceState != VoiceState.IDLE) {
                            TextButton(onClick = { viewModel.cancel() }) {
                                Text("Cancel")
                            }
                        }
                        if (uiState.voiceState == VoiceState.ERROR) {
                            TextButton(onClick = { viewModel.clearError() }) {
                                Text("Retry")
                            }
                        }
                    }

                    uiState.error?.let { errText ->
                        Spacer(modifier = Modifier.height(16.dp))
                        Surface(
                            color = MaterialTheme.colorScheme.errorContainer,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = errText,
                                color = MaterialTheme.colorScheme.onErrorContainer,
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(12.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun handleOrbTap(state: VoiceState, viewModel: VoiceViewModel) {
    when (state) {
        VoiceState.IDLE -> viewModel.startListening()
        VoiceState.LISTENING -> viewModel.stopListening()
        VoiceState.SPEAKING -> viewModel.interruptSpeaking()
        VoiceState.ERROR -> viewModel.clearError()
        VoiceState.PROCESSING -> { /* busy - ignore taps until a response or error arrives */ }
        // Phase 11 section 5: same tap-to-talk affordance as IDLE - lets
        // the user speak their yes/no answer instead of only being able
        // to use the ConfirmationDialog tap above.
        VoiceState.AWAITING_CONFIRMATION -> viewModel.startListening()
    }
}

private fun stateLabel(state: VoiceState): String = when (state) {
    VoiceState.IDLE -> "Tap to talk"
    VoiceState.LISTENING -> "Listening\u2026"
    VoiceState.PROCESSING -> "Thinking\u2026"
    VoiceState.SPEAKING -> "Speaking \u2014 tap to interrupt"
    VoiceState.ERROR -> "Something went wrong"
    VoiceState.AWAITING_CONFIRMATION -> "Say yes or no, or check the dialog below"
}

private fun outputRouteLabel(route: AudioOutputRoute): String = when (route) {
    AudioOutputRoute.SPEAKER -> "Audio: Speaker"
    AudioOutputRoute.WIRED_HEADSET -> "Audio: Wired headset"
    AudioOutputRoute.BLUETOOTH -> "Audio: Bluetooth"
}
