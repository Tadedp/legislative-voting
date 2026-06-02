package edu.um.voterterminal.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import edu.um.voterterminal.presentation.VotingState

// -- Stage Badge Color Palette --
private val BadgeGeneralColor = Color(0xFF1565C0)
private val BadgeSpecificColor = Color(0xFF6A1B9A)
private val BadgeMotionColor = Color(0xFF00838F)

/**
 * Resolves the stage string to its Spanish display label for the badge.
 *
 * Per spec §4.3:
 * - "SINGLE" → "MOCIÓN"
 * - "GENERAL" → "VOTACIÓN EN GENERAL"
 * - "SPECIFIC" → "VOTACIÓN EN PARTICULAR"
 */
private fun stageBadgeLabel(stage: String): String = when (stage) {
    "GENERAL" -> "VOTACIÓN EN GENERAL"
    "SPECIFIC" -> "VOTACIÓN EN PARTICULAR"
    else -> "MOCIÓN"
}

/** Returns the badge background color based on the stage. */
private fun stageBadgeColor(stage: String): Color = when (stage) {
    "GENERAL" -> BadgeGeneralColor
    "SPECIFIC" -> BadgeSpecificColor
    else -> BadgeMotionColor
}

@Composable
fun VotingScreen(
    state: VotingState.VotingOpen,
    isLocked: Boolean = false,
    isPresident: Boolean = false,
    presidentVotesOrdinarily: Boolean = true,
    onVoteClicked: (voteValue: String) -> Unit
) {
    // Scenario C: President whose ordinary vote is NOT required
    val presidentWaiting = isPresident && !presidentVotesOrdinarily

    val alphaValue = if (isLocked) 0.4f else 1f

    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .systemBarsPadding()
                .padding(24.dp)
                .alpha(alphaValue)
        ) {
            // ── Stage Badge ─────────────────────────────────────────
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = stageBadgeColor(state.stage)
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = stageBadgeLabel(state.stage),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = Color.White,
                        textAlign = TextAlign.Center
                    )

                    // Display the specific_reference immediately below the badge
                    // when the stage is SPECIFIC (e.g., "Artículo 4").
                    if (state.stage == "SPECIFIC" && !state.specificReference.isNullOrBlank()) {
                        Text(
                            text = state.specificReference,
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.ExtraBold,
                            color = Color.White.copy(alpha = 0.95f),
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // ── Context Panel ───────────────────────────────────────
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Text(
                        text = state.title,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = state.summary,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f)
                    )

                    Spacer(modifier = Modifier.height(24.dp))

                    // Voting Metadata Block
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.secondaryContainer
                        ),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(
                                text = "Información de la Votación",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onSecondaryContainer,
                                fontWeight = FontWeight.Bold
                            )
                            
                            val tipoVotoText = if (state.isNominal) "Votación Nominal" else "Votación Secreta"
                            Text(
                                text = "• Modalidad: $tipoVotoText",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSecondaryContainer
                            )

                            val abstencionesText = if (state.allowsAbstentions) "Permitidas" else "No permitidas"
                            Text(
                                text = "• Abstenciones: $abstencionesText",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSecondaryContainer
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            if (presidentWaiting) {
                // Scenario C: President's ordinary vote is not required — show status text
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = "Presiding Officer: Ordinary vote not required. Awaiting chamber result.",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 24.dp, vertical = 20.dp)
                    )
                }
            } else {
                // Scenarios A & B: Standard voting controls
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Button(
                            onClick = { onVoteClicked("AFFIRMATIVE") },
                            enabled = !isLocked,
                            modifier = Modifier
                                .weight(1f)
                                .height(80.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2E7D32)), // Green
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("AFIRMATIVO", style = MaterialTheme.typography.titleLarge)
                        }

                        Button(
                            onClick = { onVoteClicked("NEGATIVE") },
                            enabled = !isLocked,
                            modifier = Modifier
                                .weight(1f)
                                .height(80.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC62828)), // Red
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("NEGATIVO", style = MaterialTheme.typography.titleLarge)
                        }
                    }

                    if (state.allowsAbstentions) {
                        Button(
                            onClick = { onVoteClicked("ABSTENTION") },
                            enabled = !isLocked,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(80.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFF9A825)), // Yellow
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("ABSTENERSE", style = MaterialTheme.typography.titleLarge)
                        }
                    }
                }
            }
        }

        // Overlay for VoteLocked
        if (isLocked) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.background.copy(alpha = 0.5f)),
                contentAlignment = Alignment.Center
            ) {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                    tonalElevation = 8.dp
                ) {
                    Text(
                        text = "Voto Registrado Exitosamente",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 32.dp, vertical = 24.dp)
                    )
                }
            }
        }
    }
}
