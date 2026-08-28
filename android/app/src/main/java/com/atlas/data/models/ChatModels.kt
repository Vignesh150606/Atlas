package com.atlas.data.models

import com.google.gson.annotations.SerializedName

data class ChatRequest(
    @SerializedName("message") val message: String,
    @SerializedName("conversation_id") val conversationId: Int? = null
)

data class ChatResponse(
    @SerializedName("response") val response: String,
    @SerializedName("conversation_id") val conversationId: Int,
    @SerializedName("created_at") val createdAt: String? = null,
    // Phase 8: Android Automation Foundation. Mirrors backend
    // app/schemas/chat.py::DeviceActionSchema exactly. Nullable/absent for
    // every ordinary chat turn - only present when the Planner routed the
    // message to one of the device tools in app/tools/device_tools.py.
    @SerializedName("device_action") val deviceAction: DeviceAction? = null
)

/**
 * A directive from the backend Planner/ToolRouter for this device to
 * execute locally (see app/tools/device_tools.py on the backend for the
 * full rationale: the backend has no physical access to the phone, so it
 * can only describe what to do, not do it). Dispatched by
 * com.atlas.automation.AutomationToolRouter.
 *
 * `requiresConfirmation` (Phase 10, mission brief section 9): the backend
 * has set this field since Phase 9 (see requires_confirmation in
 * app/schemas/chat.py::DeviceActionSchema, populated from
 * CONFIRMATION_REQUIRED_ACTIONS in app/tools/device_tools.py) but this
 * class never declared it, so Gson silently dropped it on deserialization
 * and every device action executed immediately regardless of how
 * consequential it was - "requires confirmation" existed on the backend
 * only. See ChatViewModel/ConversationAudioController for where this is
 * now actually gated on before AutomationToolRouter.execute() runs.
 */
data class DeviceAction(
    @SerializedName("tool") val tool: String,
    @SerializedName("module") val module: String,
    @SerializedName("action") val action: String,
    @SerializedName("args") val args: Map<String, String> = emptyMap(),
    @SerializedName("requires_confirmation") val requiresConfirmation: Boolean = false
)

/** Mirrors backend app/schemas/chat.py::DeviceActionResultRequest. */
data class DeviceActionResultRequest(
    @SerializedName("conversation_id") val conversationId: Int,
    @SerializedName("tool") val tool: String,
    @SerializedName("action") val action: String,
    @SerializedName("success") val success: Boolean,
    @SerializedName("summary") val summary: String,
    @SerializedName("details") val details: Map<String, String> = emptyMap()
)

/** Mirrors the shape of backend app/schemas/chat.py::MessageSchema, which
 * POST /chat/device-result returns (the assistant message it created). */
data class DeviceActionResultResponse(
    @SerializedName("id") val id: Int,
    @SerializedName("role") val role: String,
    @SerializedName("content") val content: String,
    @SerializedName("created_at") val createdAt: String? = null
)

data class UiMessage(
    val id: String = java.util.UUID.randomUUID().toString(),
    val sender: MessageSender,
    val text: String,
    val timestamp: Long = System.currentTimeMillis(),
    val status: MessageStatus = MessageStatus.SENT
)

enum class MessageSender {
    USER,
    ATLAS
}

enum class MessageStatus {
    SENDING,
    SENT,
    FAILED
}
