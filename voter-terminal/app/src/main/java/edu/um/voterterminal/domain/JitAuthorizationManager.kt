package edu.um.voterterminal.domain

import edu.um.voterterminal.data.local.SecurePrefsManager
import edu.um.voterterminal.data.network.OrchestratorClient
import edu.um.voterterminal.data.network.VoteAuthorizeRequest
import edu.um.voterterminal.presentation.VotingState
import edu.um.voterterminal.security.BlindSignatureManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

sealed class AuthorizationState {
    object Idle : AuthorizationState()
    data class Required(
        val blindedTokenHex: String,
        val ephemeralPublicKeyHex: String,
        val votingRoundId: String
    ) : AuthorizationState()
    object Authorizing : AuthorizationState()
    object Authorized : AuthorizationState()
    data class Error(val message: String) : AuthorizationState()
}

@Singleton
class JitAuthorizationManager @Inject constructor(
    private val sessionManager: SessionManager,
    private val blindSignatureManager: BlindSignatureManager,
    private val orchestratorClient: OrchestratorClient,
    private val prefsManager: SecurePrefsManager
) {
    private val _authorizationState = MutableStateFlow<AuthorizationState>(AuthorizationState.Idle)
    val authorizationState: StateFlow<AuthorizationState> = _authorizationState.asStateFlow()

    private val scope = CoroutineScope(Dispatchers.IO)
    
    init {
        observeVotingRounds()
    }

    private fun observeVotingRounds() {
        scope.launch {
            sessionManager.state.collectLatest { state ->
                when (state) {
                    is VotingState.VotingRoundActive -> checkAuthorization(state)
                    else -> _authorizationState.value = AuthorizationState.Idle
                }
            }
        }
    }

    private fun checkAuthorization(state: VotingState) {
        val roundId = when (state) {
            is VotingState.VotingRoundActive -> state.votingRoundId
            else -> null
        } ?: return
        
        val ephemeralPublicKeyPem = when (state) {
            is VotingState.VotingRoundActive -> state.ephemeralPublicKey
            else -> null
        }
        
        if (ephemeralPublicKeyPem == null) return

        if (blindSignatureManager.isAuthorized(roundId)) {
            _authorizationState.value = AuthorizationState.Authorized
            return
        }

        // We need authorization. Prepare the blinded token silently.
        try {
            val (blindedTokenHex, ephemeralPublicKeyHex) = blindSignatureManager.prepareBlindedToken(
                roundId,
                ephemeralPublicKeyPem
            )
            _authorizationState.value = AuthorizationState.Required(
                blindedTokenHex = blindedTokenHex,
                ephemeralPublicKeyHex = ephemeralPublicKeyHex,
                votingRoundId = roundId
            )
        } catch (e: Exception) {
            _authorizationState.value = AuthorizationState.Error(e.message ?: "Unknown error")
        }
    }

    suspend fun submitSignature(signatureHex: String) {
        val currentState = _authorizationState.value
        if (currentState !is AuthorizationState.Required) return
        
        val legislatorId = prefsManager.legislatorId ?: return

        _authorizationState.value = AuthorizationState.Authorizing

        try {
            val request = VoteAuthorizeRequest(
                legislatorId = legislatorId,
                votingRoundId = currentState.votingRoundId,
                blindedToken = currentState.blindedTokenHex,
                ecdsaSignature = signatureHex
            )
            
            val response = orchestratorClient.authorizeVote(request)
            blindSignatureManager.setAuthorizedPayload(
                currentState.votingRoundId, 
                response.signedBlindedToken
            )
            
            _authorizationState.value = AuthorizationState.Authorized
        } catch (e: Exception) {
            _authorizationState.value = AuthorizationState.Error(e.message ?: "Failed to authorize")
        }
    }
}
