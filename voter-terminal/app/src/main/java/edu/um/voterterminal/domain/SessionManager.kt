package edu.um.voterterminal.domain

import edu.um.voterterminal.data.local.SecurePrefsManager
import edu.um.voterterminal.presentation.VotingState
import edu.um.voterterminal.security.KeyStoreManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Singleton bridging the network layer and the UI.
 * Manages the authoritative `StateFlow<VotingState>`.
 */
@Singleton
class SessionManager @Inject constructor(
    private val securePrefsManager: SecurePrefsManager,
    private val keyStoreManager: KeyStoreManager
) {
    private val _state = MutableStateFlow<VotingState>(VotingState.Unprovisioned)
    val state: StateFlow<VotingState> = _state.asStateFlow()

    fun updateState(newState: VotingState) {
        // Once revoked, we do not transition to any other state
        if (_state.value is VotingState.DeviceRevoked) return
        _state.value = newState
    }

    /**
     * Marks the current motion as successfully voted on by the user.
     * Transitions the state from VotingRoundActive to VoteLocked, retaining context.
     */
    fun markVoteSubmitted() {
        val currentState = _state.value
        if (currentState is VotingState.VotingRoundActive) {
            updateState(VotingState.VoteLocked(currentState))
        }
    }

    /**
     * Marks the presidential tie-breaker vote as successfully submitted.
     * Transitions from TieBreakerActive to TieBreakerLocked, retaining the
     * original state context so the UI remains on the distinct Gold/Purple
     * tie-breaker screen with a success overlay.
     */
    fun markTieBreakerSubmitted() {
        val currentState = _state.value
        if (currentState is VotingState.TieBreakerActive) {
            updateState(VotingState.TieBreakerLocked(currentState))
        }
    }

    /**
     * Executes the Remote Device Wipe Protocol.
     * Clears all local secure data and permanently locks the UI state.
     */
    fun executeWipeProtocol() {
        securePrefsManager.clearAll()
        keyStoreManager.clearKey()
        updateState(VotingState.DeviceRevoked)
    }
}
