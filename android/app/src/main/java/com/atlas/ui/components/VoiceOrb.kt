package com.atlas.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.dp
import com.atlas.voice.VoiceState

/**
 * A state-reactive orb for voice mode: a soft glow core with a few rotated
 * rings suggesting a wireframe sphere, entirely drawn with Compose's
 * Canvas/DrawScope primitives (radial gradients, stroked circles, an arc).
 *
 * This is a native reimplementation of an *interaction idea* - "a glowing
 * orb whose motion communicates assistant state" - not a port of any
 * particular renderer. No WebGL, no Three.js, no external graphics
 * library; colors come from MaterialTheme so it follows the app's own
 * light/dark theme instead of a fixed palette.
 */
@Composable
fun VoiceOrb(
    state: VoiceState,
    amplitude: Float = 0f,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition()

    val breathing by infiniteTransition.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        )
    )

    val rotationDurationMs = when (state) {
        VoiceState.PROCESSING -> 900
        VoiceState.LISTENING -> 6000
        VoiceState.SPEAKING -> 3000
        else -> 14000
    }
    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = rotationDurationMs, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        )
    )

    val targetScale = when (state) {
        VoiceState.LISTENING -> breathing + (amplitude.coerceIn(0f, 1f) * 0.25f)
        VoiceState.SPEAKING -> breathing + 0.08f
        VoiceState.PROCESSING -> breathing * 0.97f
        VoiceState.ERROR -> 1.0f
        VoiceState.IDLE -> breathing * 0.9f
        // Phase 11 section 5: an attentive middle ground between IDLE's
        // resting scale and LISTENING's - not actively capturing audio
        // yet, but not at rest either.
        VoiceState.AWAITING_CONFIRMATION -> breathing * 0.95f
    }
    val scale by animateFloatAsState(targetValue = targetScale, animationSpec = tween(200))

    val baseColor = when (state) {
        VoiceState.PROCESSING -> MaterialTheme.colorScheme.tertiary
        VoiceState.ERROR -> MaterialTheme.colorScheme.error
        // Phase 11 section 5: shares PROCESSING's tertiary tone ("something
        // is happening that isn't the calm default") without ERROR's
        // implication that something went wrong.
        VoiceState.AWAITING_CONFIRMATION -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.primary
    }

    val coreAlpha = when (state) {
        VoiceState.IDLE -> 0.5f
        VoiceState.LISTENING -> (0.75f + amplitude.coerceIn(0f, 1f) * 0.25f).coerceAtMost(1f)
        VoiceState.PROCESSING -> 0.65f
        VoiceState.SPEAKING -> 0.85f
        VoiceState.ERROR -> 0.7f
        VoiceState.AWAITING_CONFIRMATION -> 0.6f
    }

    Canvas(modifier = modifier.size(180.dp)) {
        val orbCenter = center
        val maxRadius = (size.minDimension / 2f) * scale

        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(baseColor.copy(alpha = coreAlpha * 0.5f), Color.Transparent),
                center = orbCenter,
                radius = maxRadius * 1.6f
            ),
            radius = maxRadius * 1.6f,
            center = orbCenter
        )

        val ringCount = 3
        for (i in 0 until ringCount) {
            val ringRadius = maxRadius * (0.55f + i * 0.16f)
            val ringDirection = if (i % 2 == 0) 1f else -0.6f
            rotate(degrees = rotation * ringDirection + (i * 40f), pivot = orbCenter) {
                drawCircle(
                    color = baseColor.copy(alpha = coreAlpha * (0.5f - i * 0.12f)),
                    radius = ringRadius,
                    center = orbCenter,
                    style = Stroke(width = 1.5.dp.toPx())
                )
            }
        }

        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(baseColor.copy(alpha = coreAlpha), baseColor.copy(alpha = coreAlpha * 0.3f)),
                center = orbCenter,
                radius = maxRadius * 0.45f
            ),
            radius = maxRadius * 0.45f,
            center = orbCenter
        )

        if (state == VoiceState.PROCESSING) {
            drawArc(
                color = baseColor.copy(alpha = 0.9f),
                startAngle = rotation,
                sweepAngle = 70f,
                useCenter = false,
                topLeft = Offset(orbCenter.x - maxRadius, orbCenter.y - maxRadius),
                size = Size(maxRadius * 2, maxRadius * 2),
                style = Stroke(width = 2.5.dp.toPx(), cap = StrokeCap.Round)
            )
        }
    }
}
