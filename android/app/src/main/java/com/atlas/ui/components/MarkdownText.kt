package com.atlas.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Minimal, defensive markdown renderer for chat bubbles.
 *
 * Supports fenced ```code blocks```, **bold**, and `inline code` only -- intentionally not a
 * full CommonMark parser. Anything it doesn't recognize is left as plain text rather than
 * risking a crash on malformed/partial markdown coming back from an LLM provider.
 */
@Composable
fun MarkdownText(
    text: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    val segments = remember(text) { splitCodeBlocks(text) }

    Column(modifier = modifier) {
        segments.forEach { segment ->
            if (segment.isCode) {
                Surface(
                    color = color.copy(alpha = 0.10f),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                ) {
                    Text(
                        text = segment.content.trim('\n'),
                        color = color,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 13.sp,
                        modifier = Modifier.padding(10.dp)
                    )
                }
            } else {
                Text(
                    text = renderInline(segment.content),
                    color = color,
                    fontSize = 15.sp
                )
            }
        }
    }
}

private data class MarkdownSegment(val content: String, val isCode: Boolean)

/** Splits on ``` fences. Odd-indexed parts (1st, 3rd, ...) are the code segments. */
private fun splitCodeBlocks(text: String): List<MarkdownSegment> {
    val parts = text.split("```")
    if (parts.size == 1) {
        return listOf(MarkdownSegment(text, isCode = false))
    }
    return parts
        .mapIndexed { index, part -> MarkdownSegment(part, isCode = index % 2 == 1) }
        .filter { it.content.isNotEmpty() }
}

/** Applies **bold** and `inline code` spans to a non-code segment. */
private fun renderInline(raw: String) = buildAnnotatedString {
    var i = 0
    val length = raw.length
    while (i < length) {
        val remaining = raw.substring(i)
        when {
            remaining.startsWith("**") -> {
                val end = raw.indexOf("**", i + 2)
                if (end == -1) {
                    append(remaining)
                    i = length
                } else {
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
                        append(raw.substring(i + 2, end))
                    }
                    i = end + 2
                }
            }
            remaining.startsWith("`") -> {
                val end = raw.indexOf("`", i + 1)
                if (end == -1) {
                    append(remaining)
                    i = length
                } else {
                    withStyle(
                        SpanStyle(
                            fontFamily = FontFamily.Monospace,
                            background = Color.Gray.copy(alpha = 0.2f)
                        )
                    ) {
                        append(raw.substring(i + 1, end))
                    }
                    i = end + 1
                }
            }
            else -> {
                append(raw[i].toString())
                i += 1
            }
        }
    }
}
