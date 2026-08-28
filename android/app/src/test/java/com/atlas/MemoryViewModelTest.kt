package com.atlas

import com.atlas.data.models.CreateMemoryRequest
import com.atlas.data.models.MemoryDto
import com.atlas.data.models.MemoryTypeEnum
import com.atlas.data.models.UpdateMemoryRequest
import com.atlas.data.repository.MemoryRepository
import com.atlas.ui.screens.memory.MemoryViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

private fun sampleMemory(
    id: String = "mem-1",
    title: String = "Favorite color",
    memoryType: String = MemoryTypeEnum.PREFERENCE.value,
    isPinned: Boolean = false
) = MemoryDto(
    id = id,
    title = title,
    content = "User's favorite color is blue",
    memoryType = memoryType,
    category = "preferences",
    importance = 3,
    isPinned = isPinned,
    source = "manual"
)

class FakeMemoryRepository : MemoryRepository {
    var shouldFail = false
    val memories = mutableListOf(sampleMemory())

    override suspend fun listMemories(
        memoryType: String?,
        category: String?,
        tag: String?,
        importance: Int?,
        isPinned: Boolean?,
        skip: Int,
        limit: Int
    ): Result<List<MemoryDto>> {
        if (shouldFail) return Result.failure(Exception("Network error"))
        val filtered = memories.filter { memoryType == null || it.memoryType == memoryType }
        return Result.success(filtered)
    }

    override suspend fun searchMemories(query: String, memoryType: String?, limit: Int): Result<List<MemoryDto>> {
        if (shouldFail) return Result.failure(Exception("Network error"))
        return Result.success(memories.filter { it.title.contains(query, ignoreCase = true) })
    }

    override suspend fun getMemory(memoryId: String): Result<MemoryDto> {
        val found = memories.find { it.id == memoryId }
        return if (found != null) Result.success(found) else Result.failure(Exception("Not found"))
    }

    override suspend fun createMemory(request: CreateMemoryRequest): Result<MemoryDto> {
        return Result.failure(Exception("Not used in these tests"))
    }

    override suspend fun updateMemory(memoryId: String, request: UpdateMemoryRequest): Result<MemoryDto> {
        if (shouldFail) return Result.failure(Exception("Network error"))
        val index = memories.indexOfFirst { it.id == memoryId }
        if (index == -1) return Result.failure(Exception("Not found"))
        val updated = memories[index].copy(isPinned = request.isPinned ?: memories[index].isPinned)
        memories[index] = updated
        return Result.success(updated)
    }

    override suspend fun deleteMemory(memoryId: String): Result<MemoryDto> {
        if (shouldFail) return Result.failure(Exception("Network error"))
        val index = memories.indexOfFirst { it.id == memoryId }
        if (index == -1) return Result.failure(Exception("Not found"))
        val removed = memories.removeAt(index)
        return Result.success(removed)
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class MemoryViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var fakeRepository: FakeMemoryRepository
    private lateinit var viewModel: MemoryViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        fakeRepository = FakeMemoryRepository()
        viewModel = MemoryViewModel(fakeRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testLoadsMemoriesOnInit() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        val state = viewModel.uiState.value
        assertEquals(1, state.memories.size)
        assertEquals("Favorite color", state.memories[0].title)
        assertFalse(state.isLoading)
    }

    @Test
    fun testLoadFailureSetsError() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        fakeRepository.shouldFail = true

        viewModel.loadMemories()
        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertNotNull(state.error)
        assertFalse(state.isLoading)
    }

    @Test
    fun testTogglePinnedUpdatesMemoryInPlace() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        val memory = viewModel.uiState.value.memories[0]
        assertFalse(memory.isPinned)

        viewModel.togglePinned(memory)
        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(1, state.memories.size)
        assertTrue(state.memories[0].isPinned)
    }

    @Test
    fun testDeleteMemoryRemovesItFromList() = runTest {
        testDispatcher.scheduler.advanceUntilIdle()
        val memoryId = viewModel.uiState.value.memories[0].id

        viewModel.deleteMemory(memoryId)
        testDispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.memories.isEmpty())
    }
}
