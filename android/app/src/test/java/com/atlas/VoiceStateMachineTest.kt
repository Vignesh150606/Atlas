package com.atlas

import com.atlas.voice.VoiceState
import com.atlas.voice.VoiceStateMachine
import org.junit.Assert.*
import org.junit.Test

class VoiceStateMachineTest {

    @Test
    fun testInitialStateIsIdle() {
        val machine = VoiceStateMachine()
        assertEquals(VoiceState.IDLE, machine.current)
    }

    @Test
    fun testValidHappyPathTransitions() {
        val machine = VoiceStateMachine()
        assertTrue(machine.transitionTo(VoiceState.LISTENING))
        assertTrue(machine.transitionTo(VoiceState.PROCESSING))
        assertTrue(machine.transitionTo(VoiceState.SPEAKING))
        assertTrue(machine.transitionTo(VoiceState.IDLE))
        assertEquals(VoiceState.IDLE, machine.current)
    }

    @Test
    fun testContinuousConversationTurnTakingSpeakingBackToListening() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        machine.transitionTo(VoiceState.PROCESSING)
        machine.transitionTo(VoiceState.SPEAKING)
        assertTrue(machine.transitionTo(VoiceState.LISTENING))
        assertEquals(VoiceState.LISTENING, machine.current)
    }

    @Test
    fun testSpeakingCanSpeakVerifiedResultWhileAlreadySpeaking() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        machine.transitionTo(VoiceState.PROCESSING)
        machine.transitionTo(VoiceState.SPEAKING)

        assertTrue(machine.transitionTo(VoiceState.SPEAKING))
        assertEquals(VoiceState.SPEAKING, machine.current)
    }

    @Test
    fun testCannotSkipDirectlyFromIdleToProcessingOrSpeaking() {
        val machine = VoiceStateMachine()
        assertFalse(machine.transitionTo(VoiceState.PROCESSING))
        assertFalse(machine.transitionTo(VoiceState.SPEAKING))
        assertEquals(VoiceState.IDLE, machine.current)
    }

    @Test
    fun testIdleIsAlwaysReachableAsTheCancelResetEscape() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        assertTrue(machine.transitionTo(VoiceState.IDLE))

        machine.transitionTo(VoiceState.LISTENING)
        machine.transitionTo(VoiceState.PROCESSING)
        assertTrue(machine.transitionTo(VoiceState.IDLE))

        machine.transitionTo(VoiceState.LISTENING)
        machine.transitionTo(VoiceState.PROCESSING)
        machine.transitionTo(VoiceState.SPEAKING)
        assertTrue(machine.transitionTo(VoiceState.IDLE))
    }

    @Test
    fun testErrorStateOnlyEscapesViaIdleReset() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        machine.transitionTo(VoiceState.ERROR)

        assertFalse(machine.transitionTo(VoiceState.LISTENING))
        assertFalse(machine.transitionTo(VoiceState.SPEAKING))
        assertFalse(machine.transitionTo(VoiceState.PROCESSING))
        assertTrue(machine.transitionTo(VoiceState.IDLE))
    }

    @Test
    fun testResetReturnsToIdleUnconditionally() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        machine.transitionTo(VoiceState.PROCESSING)
        machine.reset()
        assertEquals(VoiceState.IDLE, machine.current)
    }

    @Test
    fun testListeningCanTransitionToError() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        assertTrue(machine.transitionTo(VoiceState.ERROR))
    }

    @Test
    fun testProcessingCanTransitionToError() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        machine.transitionTo(VoiceState.PROCESSING)
        assertTrue(machine.transitionTo(VoiceState.ERROR))
    }

    @Test
    fun testRejectedTransitionDoesNotChangeState() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.LISTENING)
        val before = machine.current
        machine.transitionTo(VoiceState.SPEAKING) // LISTENING -> SPEAKING is not allowed
        assertEquals(before, machine.current)
    }

    @Test
    fun testIdleCanEnterAwaitingConfirmation() {
        val machine = VoiceStateMachine()
        assertTrue(machine.transitionTo(VoiceState.AWAITING_CONFIRMATION))
        assertEquals(VoiceState.AWAITING_CONFIRMATION, machine.current)
    }

    @Test
    fun testAwaitingConfirmationCanTransitionToListening() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.AWAITING_CONFIRMATION)
        assertTrue(machine.transitionTo(VoiceState.LISTENING))
        assertEquals(VoiceState.LISTENING, machine.current)
    }

    @Test
    fun testAwaitingConfirmationCanTransitionToError() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.AWAITING_CONFIRMATION)
        assertTrue(machine.transitionTo(VoiceState.ERROR))
    }

    @Test
    fun testAwaitingConfirmationCannotSkipDirectlyToProcessingOrSpeaking() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.AWAITING_CONFIRMATION)
        assertFalse(machine.transitionTo(VoiceState.PROCESSING))
        assertFalse(machine.transitionTo(VoiceState.SPEAKING))
        assertEquals(VoiceState.AWAITING_CONFIRMATION, machine.current)
    }

    @Test
    fun testAwaitingConfirmationCanAlwaysEscapeToIdle() {
        val machine = VoiceStateMachine()
        machine.transitionTo(VoiceState.AWAITING_CONFIRMATION)
        assertTrue(machine.transitionTo(VoiceState.IDLE))
    }
}
