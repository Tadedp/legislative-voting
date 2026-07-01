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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import edu.um.voterterminal.R
import edu.um.voterterminal.presentation.VotingState
import edu.um.voterterminal.domain.AuthorizationState

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
@Composable
private fun stageBadgeLabel(stage: String): String = when (stage) {
    "GENERAL" -> stringResource(R.string.voting_general)
    "SPECIFIC" -> stringResource(R.string.voting_specific)
    else -> stringResource(R.string.motion)
}

/** Returns the badge background color based on the stage. */
private fun stageBadgeColor(stage: String): Color = when (stage) {
    "GENERAL" -> BadgeGeneralColor
    "SPECIFIC" -> BadgeSpecificColor
    else -> BadgeMotionColor
}

@Composable
fun VotingScreen(
    state: VotingState.VotingRoundActive,
    isLocked: Boolean = false,
    isPresident: Boolean = false,
    presidentVotesOrdinarily: Boolean = true,
    remainingTimeSeconds: Int? = null,
    volatileSalt: String? = null,
    authorizationState: AuthorizationState = AuthorizationState.Idle,
    onAuthorizeClicked: () -> Unit = {},
    onRetryAuthorizeClicked: () -> Unit = {},
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
                                text = stringResource(R.string.voting_info),
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onSecondaryContainer,
                                fontWeight = FontWeight.Bold
                            )
                            
                            val tipoVotoText = if (state.isNominal) stringResource(R.string.voting_nominal) else stringResource(R.string.voting_secret)
                            Text(
                                text = stringResource(R.string.modality, tipoVotoText),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSecondaryContainer
                            )

                            val abstencionesText = if (state.allowsAbstentions) stringResource(R.string.allowed) else stringResource(R.string.not_allowed)
                            Text(
                                text = stringResource(R.string.abstentions_status, abstencionesText),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSecondaryContainer
                            )
                        }
                    }

                    if (remainingTimeSeconds != null) {
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = stringResource(R.string.time_remaining, remainingTimeSeconds),
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.Black,
                            color = if (remainingTimeSeconds <= 10) Color.Red else MaterialTheme.colorScheme.error,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
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
                        text = stringResource(R.string.president_waiting),
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
                            enabled = !isLocked && authorizationState is AuthorizationState.Authorized,
                            modifier = Modifier
                                .weight(1f)
                                .height(80.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2E7D32)), // Green
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(stringResource(R.string.affirmative), style = MaterialTheme.typography.titleLarge)
                        }

                        Button(
                            onClick = { onVoteClicked("NEGATIVE") },
                            enabled = !isLocked && authorizationState is AuthorizationState.Authorized,
                            modifier = Modifier
                                .weight(1f)
                                .height(80.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC62828)), // Red
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(stringResource(R.string.negative), style = MaterialTheme.typography.titleLarge)
                        }
                    }

                    if (state.allowsAbstentions) {
                        Button(
                            onClick = { onVoteClicked("ABSTENTION") },
                            enabled = !isLocked && authorizationState is AuthorizationState.Authorized,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(80.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFF9A825)), // Yellow
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(stringResource(R.string.abstain), style = MaterialTheme.typography.titleLarge)
                        }
                    }
                }
                
                if (authorizationState !is AuthorizationState.Authorized && !presidentWaiting) {
                    Spacer(modifier = Modifier.height(16.dp))
                    if (authorizationState is AuthorizationState.Error) {
                        Button(
                            onClick = onRetryAuthorizeClicked,
                            enabled = !isLocked,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(60.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("Reintentar Acreditación", style = MaterialTheme.typography.titleMedium)
                        }
                    } else {
                        Button(
                            onClick = onAuthorizeClicked,
                            enabled = !isLocked && authorizationState is AuthorizationState.Required,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(60.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("Acreditar Identidad para Votar", style = MaterialTheme.typography.titleMedium)
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
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.padding(horizontal = 32.dp, vertical = 24.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.vote_registered),
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                            textAlign = TextAlign.Center
                        )
                        if (volatileSalt != null) {
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = stringResource(R.string.verification_code_label, volatileSalt),
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onPrimaryContainer,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = stringResource(R.string.verification_code_warning),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.error,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }
            }
        }
    }
}
