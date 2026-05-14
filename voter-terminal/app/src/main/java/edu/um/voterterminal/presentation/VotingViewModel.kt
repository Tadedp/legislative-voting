package edu.um.voterterminal.presentation

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import edu.um.voterterminal.data.local.SecurePrefsManager
import edu.um.voterterminal.data.network.OrchestratorClient
import edu.um.voterterminal.domain.SessionManager
import edu.um.voterterminal.service.SessionKeepAliveService
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class VotingViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val sessionManager: SessionManager,
    private val securePrefsManager: SecurePrefsManager,
    private val orchestratorClient: OrchestratorClient
) : ViewModel() {

    val uiState: StateFlow<VotingState> = sessionManager.state

    init {
        initializeSession()
    }

    private fun initializeSession() {
        if (securePrefsManager.deviceToken == null) {
            sessionManager.updateState(VotingState.Unprovisioned)
            return
        }

        // If enrolled, synchronously fetch the current session state via REST
        viewModelScope.launch {
            try {
                val sessionResponse = orchestratorClient.getCurrentSession()
                
                // Map the REST response to our initial UI state
                val initialState = if (sessionResponse.status == "VOTING_OPEN") {
                    // In a full implementation, the GET /sessions/current response would include
                    // the current motion details. For now, we transition to Idle if we lack motion details.
                    // Assuming the Orchestrator will immediately push a MOTION_OPENED via WS upon connect.
                    VotingState.Idle
                } else {
                    VotingState.Idle
                }
                
                sessionManager.updateState(initialState)
                
                // Start the Foreground Service to maintain the WebSocket connection
                startKeepAliveService()
            } catch (e: Exception) {
                // If the network request fails, we stay in whatever state we are,
                // or we could define an Error state. We will retry or just start the service
                // which has its own backoff logic for the WebSocket.
                startKeepAliveService()
            }
        }
    }

    private fun startKeepAliveService() {
        val intent = Intent(context, SessionKeepAliveService::class.java)
        ContextCompat.startForegroundService(context, intent)
    }

    /**
     * Called by the UI after successfully POSTing a vote to the REST API.
     */
    fun markVoteSubmitted(motionId: String) {
        sessionManager.markVoteSubmitted(motionId)
    }
}
