package com.atlas

import com.atlas.voice.ConfirmationAnswer
import com.atlas.voice.ConfirmationYesNoClassifier
import org.junit.Assert.assertEquals
import org.junit.Test

class ConfirmationYesNoClassifierTest {

    @Test
    fun testPlainYesVariants() {
        for (text in listOf("yes", "Yes", "yeah", "yep", "yup", "sure", "confirm", "ok", "okay")) {
            assertEquals("expected YES for '$text'", ConfirmationAnswer.YES, ConfirmationYesNoClassifier.classify(text))
        }
    }

    @Test
    fun testYesWithTrailingWords() {
        assertEquals(ConfirmationAnswer.YES, ConfirmationYesNoClassifier.classify("yes, go ahead"))
        assertEquals(ConfirmationAnswer.YES, ConfirmationYesNoClassifier.classify("yeah do it"))
        assertEquals(ConfirmationAnswer.YES, ConfirmationYesNoClassifier.classify("go ahead and call him"))
    }

    @Test
    fun testPlainNoVariants() {
        for (text in listOf("no", "No", "nope", "nah", "cancel", "don't", "stop")) {
            assertEquals("expected NO for '$text'", ConfirmationAnswer.NO, ConfirmationYesNoClassifier.classify(text))
        }
    }

    @Test
    fun testNoWithTrailingWords() {
        assertEquals(ConfirmationAnswer.NO, ConfirmationYesNoClassifier.classify("no, don't do that"))
        assertEquals(ConfirmationAnswer.NO, ConfirmationYesNoClassifier.classify("cancel that"))
        assertEquals(ConfirmationAnswer.NO, ConfirmationYesNoClassifier.classify("never mind"))
    }

    @Test
    fun testUnrelatedTextIsUnclear() {
        assertEquals(ConfirmationAnswer.UNCLEAR, ConfirmationYesNoClassifier.classify("what's the weather today"))
        assertEquals(ConfirmationAnswer.UNCLEAR, ConfirmationYesNoClassifier.classify(""))
        assertEquals(ConfirmationAnswer.UNCLEAR, ConfirmationYesNoClassifier.classify("   "))
    }

    @Test
    fun testMidSentenceYesOrNoDoesNotMatch() {
        // Anchored to the start on purpose - a "no" or "yes" appearing
        // later in an unrelated sentence must not be picked up.
        assertEquals(ConfirmationAnswer.UNCLEAR, ConfirmationYesNoClassifier.classify("I have no idea what you mean"))
        assertEquals(ConfirmationAnswer.UNCLEAR, ConfirmationYesNoClassifier.classify("remind me about yes that thing"))
    }

    @Test
    fun testCaseAndWhitespaceInsensitive() {
        assertEquals(ConfirmationAnswer.YES, ConfirmationYesNoClassifier.classify("  YES  "))
        assertEquals(ConfirmationAnswer.NO, ConfirmationYesNoClassifier.classify("  Cancel  "))
    }
}
