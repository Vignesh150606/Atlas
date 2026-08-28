package com.atlas.ui.components

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import com.atlas.data.models.DeviceAction

/**
 * Phase 10 (mission brief section 9): the confirmation UI for a
 * DeviceAction with requiresConfirmation=true. Shared by ChatScreen and
 * VoiceScreen (see those files) so a consequential action - e.g. a
 * clipboard write or a phone dial, see CONFIRMATION_REQUIRED_ACTIONS in
 * app/tools/device_tools.py on the backend - is never executed without
 * an explicit tap, in either mode.
 *
 * Deliberately renders the raw module/action/args rather than trying to
 * generate a friendly sentence per action type: a small, fixed set of
 * action types will always outgrow a hardcoded phrase table, and an
 * honest "here's exactly what will run" is safer for a confirmation
 * prompt than a paraphrase that could drift from what actually executes.
 */
@Composable
fun ConfirmationDialog(
    action: DeviceAction,
    onConfirm: () -> Unit,
    onCancel: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Confirm this action") },
        text = {
            Text(describeAction(action))
        },
        confirmButton = {
            TextButton(onClick = onConfirm) { Text("Confirm") }
        },
        dismissButton = {
            TextButton(onClick = onCancel) { Text("Cancel") }
        }
    )
}

private fun describeAction(action: DeviceAction): String {
    val argsText = if (action.args.isEmpty()) "" else "\n\n" + action.args.entries.joinToString("\n") { (key, value) -> "$key: $value" }
    return "ATLAS wants to perform \"${action.action}\" (${action.module}).$argsText"
}
