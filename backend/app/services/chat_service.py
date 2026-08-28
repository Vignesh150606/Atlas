from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.providers.base import LLMProvider, ProviderError
from app.schemas.chat import ChatRequest, ChatResponse, DeviceActionSchema
from app.tools.base import ToolResult
from app.memory.memory_extractor import MemoryExtractor
from app.services.memory_service import MemoryService
from app.services.conversation_service import ConversationService
from app.services.conversation_intelligence import ConversationIntelligenceService
from app.retrieval.retrieval_service import RetrievalService
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService
from app.repositories.memory_repository import MemoryRepository
from app.prompts.prompt_builder import PromptBuilder
from app.schemas.memory import MemoryCreate
from app.intent.intent_service import IntentService
from app.planner.planner import Planner
from app.tools.router import ToolRouter
from app.observability.trace import RequestTrace
from app.core.config import settings


class ChatService:
    """Orchestrates a full chat turn through the cognitive pipeline:

        User -> Intent Analysis -> Memory Retrieval -> Tool Selection ->
        Reasoning Plan -> Prompt Construction -> LLM -> Memory Update -> Response

    Concretely, in order:
    1. Get or create the conversation.
    2. Fetch prior history with rollover (context-window trimmed; older
       messages beyond the window get a short summary note instead of being
       silently dropped) - BEFORE persisting the current message.
    3. Classify intent (deterministic, no LLM) and build an execution plan
       (which tools to call, whether memory/knowledge retrieval is needed).
    4. Persist the user's message immediately, so it isn't lost if the
       provider call fails downstream.
    5. Run rule-based memory extraction on the incoming message (unchanged
       from Phase 3) - counted in the trace as a memory update.
    6. Dispatch any tools the plan called for (timetable/calculator/memory/
       document/knowledge/timeline/project/summary - Phase 6 added the last
       five).
    7. Retrieve relevant memories via structured, ranked retrieval - only if
       the plan says this intent actually needs it (a "hello" doesn't).
    7b. Retrieve relevant imported documents the same way (Phase 6) - same
        "only if the plan says so" gating, same no-vectors philosophy.
    8. Build the prompt (system + developer + date/time + provider + plan +
       tool results + retrieved memory + retrieved documents + user profile
       + history + message).
    9. Call the provider.
    10. Persist the assistant's reply, log a structured trace, and return.
    """

    def __init__(self, db: AsyncSession, provider: LLMProvider):
        self.db = db
        self.provider = provider
        self.conversation_service = ConversationService(db)
        self.conversation_intelligence = ConversationIntelligenceService(db)
        self.retrieval_service = RetrievalService(db)
        self.knowledge_retrieval_service = KnowledgeRetrievalService(db)
        self.memory_repository = MemoryRepository(db)
        self.memory_service = MemoryService(db)
        self.tool_router = ToolRouter(db)

    async def process_chat(self, chat_request: ChatRequest) -> ChatResponse:
        trace = RequestTrace(provider=self.provider.name)

        try:
            return await self._process_chat(chat_request, trace)
        except Exception as e:
            trace.error = str(e)
            raise
        finally:
            trace.log()

    async def _process_chat(self, chat_request: ChatRequest, trace: RequestTrace) -> ChatResponse:
        conversation = await self.conversation_service.get_or_create(chat_request.conversation_id)
        trace.conversation_id = conversation.id

        # Fetch history (with rollover summarization) before this turn's
        # message exists in the DB.
        history, rollover_note = await self.conversation_intelligence.get_history_with_rollover(
            conversation.id, max_messages=settings.MAX_HISTORY_MESSAGES
        )

        # --- Intent Analysis + Reasoning Plan (deterministic, no LLM) ---
        intent_result = IntentService.classify(chat_request.message)
        plan = Planner.build_plan(chat_request.message, intent_result)
        trace.intent = intent_result.intent.value
        trace.intent_confidence = intent_result.confidence
        trace.planner_notes = plan.notes

        # Persist the user's message right away so it survives a downstream
        # provider failure.
        await self.conversation_service.save_user_message(conversation.id, chat_request.message)

        # Rule-based memory extraction (unchanged behavior from Phase 3).
        for ext in MemoryExtractor.extract_from_text(chat_request.message):
            # Check duplication ourselves so the trace only counts genuinely
            # new memories - create_memory() always returns a Memory (even
            # for an existing duplicate), so its return value alone can't
            # distinguish "created" from "found existing".
            is_new = await self.memory_repository.find_duplicate(
                ext.title, ext.content, memory_type=ext.memory_type.value
            ) is None
            mem_create = MemoryCreate(
                title=ext.title,
                content=ext.content,
                memory_type=ext.memory_type,
                category=ext.category,
                importance=ext.importance,
                source="chat_extraction",
                tags=ext.tags,
                structured_data=ext.structured_data,
            )
            await self.memory_service.create_memory(mem_create, allow_duplicate=False)
            if is_new:
                trace.memory_updates += 1

        # --- Tool Selection / dispatch ---
        tool_results = []
        for call in plan.tool_calls:
            trace.tools_selected.append(call.tool)
            result = await self.tool_router.dispatch(call.tool, **call.args)
            if result.success:
                trace.tools_succeeded.append(call.tool)
            else:
                trace.tools_failed.append(call.tool)
            tool_results.append(result)

        # --- Memory Retrieval (only if the plan says this intent needs it) ---
        retrieved_memories = []
        if plan.needs_memory_retrieval:
            history_text = " ".join(m["content"] for m in history[-6:])  # recent turns only, for context scoring
            retrieved_memories = await self.retrieval_service.retrieve(
                chat_request.message, history_text=history_text
            )
        trace.retrieved_memory_count = len(retrieved_memories)
        trace.retrieved_memory_ids = [m.id for m in retrieved_memories]

        # --- Knowledge Retrieval (Phase 6, same gating as memory retrieval) ---
        retrieved_documents = []
        if plan.needs_knowledge_retrieval:
            retrieved_documents = await self.knowledge_retrieval_service.retrieve_documents(
                chat_request.message
            )
        trace.retrieved_document_count = len(retrieved_documents)
        trace.retrieved_document_ids = [d.id for d in retrieved_documents]

        # Small, always-on "user profile" section from pinned memories -
        # ATLAS has no dedicated profile entity, so this is the closest
        # honest equivalent (see PromptBuilder._format_user_profile).
        pinned_memories = await self.memory_repository.get_filtered(is_pinned=True, limit=3)

        # --- Phase 9: Conversation Intelligence hints ---
        # Deterministic, cheap checks - no extra DB query or provider call,
        # just pattern matching over the current message (and, for
        # follow-up detection, the history already fetched above).
        conversation_hints: List[str] = []
        follow_up = self.conversation_intelligence.detect_follow_up(chat_request.message, history)
        if follow_up:
            conversation_hints.append(follow_up.hint)
            trace.follow_up_detected = True
        ambiguity_note = self.conversation_intelligence.detect_ambiguous_command(chat_request.message)
        if ambiguity_note:
            conversation_hints.append(ambiguity_note)
            trace.ambiguity_detected = True

        # --- Context Builder ---
        prompt_context = PromptBuilder.build(
            history=history,
            current_message=chat_request.message,
            retrieved_memories=retrieved_memories,
            retrieved_documents=retrieved_documents,
            provider_name=self.provider.name,
            plan=plan,
            tool_results=tool_results,
            user_profile_memories=pinned_memories,
            conversation_summary=rollover_note,
            conversation_hints=conversation_hints,
        )

        try:
            ai_response_text = await self.provider.generate_response(
                messages=prompt_context.messages,
                system_prompt=prompt_context.system_prompt,
            )
        except ProviderError as e:
            # Surface a clean error rather than a raw exception; the user's
            # message is already saved, so nothing is lost.
            ai_response_text = f"[ATLAS could not reach the {self.provider.name} provider: {e}]"
            trace.error = str(e)

        assistant_msg = await self.conversation_service.save_assistant_message(
            conversation.id, ai_response_text
        )

        await self.db.commit()

        device_action = self._extract_device_action(tool_results)
        trace.device_action = device_action.tool if device_action else None

        return ChatResponse(
            response=ai_response_text,
            conversation_id=conversation.id,
            created_at=assistant_msg.created_at,
            device_action=device_action,
        )

    @staticmethod
    def _extract_device_action(tool_results: List[ToolResult]) -> Optional[DeviceActionSchema]:
        """Phase 8: lifts the first successful device_action out of this
        turn's tool results onto the response. See app/tools/device_tools.py
        for why at most one is ever produced by the Planner in practice -
        this still only takes the first defensively, in case that
        invariant ever changes."""
        for result in tool_results:
            if result.success and result.device_action:
                directive = result.device_action
                return DeviceActionSchema(
                    tool=result.tool_name,
                    module=directive.get("module", ""),
                    action=directive.get("action", ""),
                    args=directive.get("args", {}) or {},
                    requires_confirmation=result.requires_confirmation,
                )
        return None
