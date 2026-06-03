package edu.um.voterterminal

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.Crossfade
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.viewmodel.compose.viewModel
import dagger.hilt.android.AndroidEntryPoint
import edu.um.voterterminal.presentation.VotingState
import edu.um.voterterminal.presentation.VotingViewModel
import edu.um.voterterminal.ui.screens.DeviceRevokedScreen
import edu.um.voterterminal.ui.screens.IdleScreen
import edu.um.voterterminal.ui.screens.MotionTiedIdleScreen
import edu.um.voterterminal.ui.screens.DebateIdleScreen
import edu.um.voterterminal.ui.screens.ProvisioningScreen
import edu.um.voterterminal.ui.screens.TieBreakerScreen
import edu.um.voterterminal.ui.screens.VotingScreen
import edu.um.voterterminal.ui.theme.VoterTerminalTheme

@AndroidEntryPoint
class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Security Mitigation: Tapjacking Protection
        // Prevents malicious overlays from capturing touch events
        window.decorView.filterTouchesWhenObscured = true

        enableEdgeToEdge()
        setContent {
            VoterTerminalTheme {
                val viewModel: VotingViewModel = viewModel()
                val uiState by viewModel.uiState.collectAsState()

                // Security Mitigation: Dynamic Screen Wake Lock
                // Keeps Wi-Fi active and screen on during critical voting states
                LaunchedEffect(uiState) {
                    val keepScreenOn = uiState is VotingState.VotingRoundActive
                            || uiState is VotingState.TieBreakerActive
                    if (keepScreenOn) {
                        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    } else {
                        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    }
                }

                val remainingTime by viewModel.remainingTimeSeconds.collectAsState()

                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    VoterTerminalRouter(
                        uiState = uiState,
                        activity = this@MainActivity,
                        viewModel = viewModel,
                        remainingTimeSeconds = remainingTime
                    )
                }
            }
        }
    }
}

@Composable
fun VoterTerminalRouter(
    uiState: VotingState,
    activity: FragmentActivity,
    viewModel: VotingViewModel,
    remainingTimeSeconds: Int?
) {
    Crossfade(targetState = uiState, label = "Router") { state ->
        when (state) {
            is VotingState.Unprovisioned -> {
                ProvisioningScreen(
                    onProvisionClicked = { nationalId, adminUsername, adminPassword ->
                        viewModel.provisionDevice(nationalId, adminUsername, adminPassword)
                    }
                )
            }
            is VotingState.Idle -> {
                IdleScreen()
            }
            is VotingState.DebateIdle -> {
                DebateIdleScreen(state = state)
            }
            is VotingState.VotingRoundActive -> {
                // Presidential identity comparison for UI forking
                val isPresident = viewModel.legislatorId != null
                        && viewModel.legislatorId == state.presidingOfficerId
                VotingScreen(
                    state = state,
                    isLocked = state.status != "VOTING_OPEN",
                    isPresident = isPresident,
                    presidentVotesOrdinarily = state.presidentVotesOrdinarily,
                    remainingTimeSeconds = remainingTimeSeconds,
                    onVoteClicked = { voteValue ->
                        viewModel.submitVote(activity, voteValue)
                    }
                )
            }
            is VotingState.VoteLocked -> {
                VotingScreen(
                    state = state.originalState,
                    isLocked = true,
                    remainingTimeSeconds = remainingTimeSeconds,
                    onVoteClicked = { /* Ignored — vote already submitted */ }
                )
            }
            is VotingState.MotionTiedIdle -> {
                MotionTiedIdleScreen()
            }
            is VotingState.TieBreakerActive -> {
                TieBreakerScreen(
                    state = state,
                    isLocked = false,
                    onVoteClicked = { voteValue ->
                        viewModel.submitTieBreakerVote(activity, voteValue)
                    }
                )
            }
            is VotingState.TieBreakerLocked -> {
                TieBreakerScreen(
                    state = state.originalState,
                    isLocked = true,
                    onVoteClicked = { /* Ignored — tie-breaker vote already submitted */ }
                )
            }
            is VotingState.DeviceRevoked -> {
                DeviceRevokedScreen()
            }
        }
    }
}