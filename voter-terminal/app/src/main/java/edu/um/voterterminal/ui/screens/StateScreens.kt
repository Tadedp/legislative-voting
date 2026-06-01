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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import edu.um.voterterminal.presentation.VotingState

@Composable
fun IdleScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .systemBarsPadding()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        CircularProgressIndicator(
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(bottom = 24.dp)
        )
        Text(
            text = "Esperando Próxima Moción",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onBackground
        )
        Text(
            text = "La presidencia aún no ha abierto una moción para votar. Por favor aguarde.",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 16.dp)
        )
    }
}

@Composable
fun DeviceRevokedScreen() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.errorContainer)
            .systemBarsPadding()
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "DISPOSITIVO REVOCADO",
                style = MaterialTheme.typography.displayMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onErrorContainer,
                textAlign = TextAlign.Center
            )
            Text(
                text = "Este terminal ha sido deshabilitado permanentemente por el Orquestador. Todo el material seguro ha sido borrado.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.8f),
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 16.dp)
            )
        }
    }
}

/**
 * Screen displayed to standard legislators (non-presidents) when a motion
 * results in a tie. Shows a waiting indicator while the presiding officer
 * casts the deciding vote.
 */
@Composable
fun MotionTiedIdleScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .systemBarsPadding()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        CircularProgressIndicator(
            color = TieBreakerGold,
            modifier = Modifier.padding(bottom = 24.dp)
        )
        Text(
            text = "Moción Empatada",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground
        )
        Text(
            text = "Moción Empatada. Aguardando Desempate Presidencial.",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 16.dp)
        )
    }
}

// -- Tie-Breaker Color Palette (Gold / Deep Purple) --
private val TieBreakerGold = Color(0xFFFFD600)
private val TieBreakerDeepPurple = Color(0xFF4A148C)
private val TieBreakerOnGold = Color(0xFF1A1A1A)

/**
 * Visually distinct voting screen for the presiding officer's tie-breaker vote.
 *
 * Uses a Gold/Deep Purple accent palette to clearly differentiate from
 * the standard voting interface. Only two options are available:
 * AFFIRMATIVE and NEGATIVE (no abstention on a tie-break).
 *
 * @param state The [VotingState.TieBreakerActive] containing the tied motion metadata.
 * @param isLocked True when the tie-breaker vote has been submitted (shows dimmed overlay).
 * @param onVoteClicked Callback invoked with the deciding vote value.
 */
@Composable
fun TieBreakerScreen(
    state: VotingState.TieBreakerActive,
    isLocked: Boolean = false,
    onVoteClicked: (voteValue: String) -> Unit
) {
    val alphaValue = if (isLocked) 0.4f else 1f

    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            TieBreakerDeepPurple,
                            TieBreakerDeepPurple.copy(alpha = 0.85f)
                        )
                    )
                )
                .systemBarsPadding()
                .padding(24.dp)
                .alpha(alphaValue)
        ) {
            // Urgent header banner
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = TieBreakerGold),
                shape = RoundedCornerShape(12.dp)
            ) {
                Text(
                    text = "EMPATE DETECTADO: Emita Voto de Desempate",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TieBreakerOnGold,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp)
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Motion context panel
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                colors = CardDefaults.cardColors(
                    containerColor = Color.White.copy(alpha = 0.12f)
                ),
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
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = state.summary,
                        style = MaterialTheme.typography.bodyLarge,
                        color = Color.White.copy(alpha = 0.8f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Tie-breaker voting controls — AFFIRMATIVE / NEGATIVE only (no abstention)
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
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2E7D32)),
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
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC62828)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text("NEGATIVO", style = MaterialTheme.typography.titleLarge)
                }
            }
        }

        // Overlay for TieBreakerLocked — Gold accent to stay visually coherent
        if (isLocked) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(TieBreakerDeepPurple.copy(alpha = 0.5f)),
                contentAlignment = Alignment.Center
            ) {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = TieBreakerGold,
                    tonalElevation = 8.dp
                ) {
                    Text(
                        text = "Voto de Desempate Registrado Exitosamente",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        color = TieBreakerOnGold,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 32.dp, vertical = 24.dp)
                    )
                }
            }
        }
    }
}
