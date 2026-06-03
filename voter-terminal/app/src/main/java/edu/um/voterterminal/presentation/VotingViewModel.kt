package edu.um.voterterminal.presentation

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import edu.um.voterterminal.data.local.SecurePrefsManager
import edu.um.voterterminal.data.network.EnrollRequest
import edu.um.voterterminal.data.network.LoginRequest
import edu.um.voterterminal.data.network.NominalVoteRequest
import edu.um.voterterminal.data.network.NonNominalVoteRequest
import edu.um.voterterminal.data.network.OrchestratorClient
import edu.um.voterterminal.domain.SessionManager
import edu.um.voterterminal.security.BiometricSigner
import edu.um.voterterminal.security.EncryptionUtils
import edu.um.voterterminal.security.KeyStoreManager
import edu.um.voterterminal.security.PayloadCanonicalizer
import edu.um.voterterminal.service.SessionKeepAliveService
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.UUID
import javax.inject.Inject

@HiltViewModel
class VotingViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val sessionManager: SessionManager,
    private val securePrefsManager: SecurePrefsManager,
    private val orchestratorClient: OrchestratorClient,
    private val keyStoreManager: KeyStoreManager,
    private val encryptionUtils: EncryptionUtils,
    private val biometricSigner: BiometricSigner
) : ViewModel() {

    val uiState: StateFlow<VotingState> = sessionManager.state

    /** Exposes the locally stored legislator ID for presidential identity checks in the UI layer. */
    val legislatorId: String?
        get() = securePrefsManager.legislatorId

    private val _remainingTimeSeconds = MutableStateFlow<Int?>(null)
    val remainingTimeSeconds: StateFlow<Int?> = _remainingTimeSeconds

    private var timerJob: kotlinx.coroutines.Job? = null

    init {
        initializeSession()
        
        // Launch a collector to monitor VotingRoundActive states for the countdown timer
        viewModelScope.launch {
            sessionManager.state.collect { state ->
                if (state is VotingState.VotingRoundActive && state.status == "VOTING_OPEN" && state.timeLimitSeconds != null) {
                    startTimer(state.timeLimitSeconds)
                } else if (state is VotingState.VoteLocked && state.originalState.status == "VOTING_OPEN" && state.originalState.timeLimitSeconds != null) {
                    // Let timer keep running if we just locked our own vote
                } else {
                    stopTimer()
                }
            }
        }
    }

    private fun startTimer(limit: Int) {
        if (timerJob?.isActive == true) return
        timerJob = viewModelScope.launch {
            for (i in limit downTo 0) {
                _remainingTimeSeconds.value = i
                kotlinx.coroutines.delay(1000)
            }
        }
    }

    private fun stopTimer() {
        timerJob?.cancel()
        timerJob = null
        _remainingTimeSeconds.value = null
    }

    /**
     * Hydrates the terminal state from the Orchestrator REST API.
     */
    private fun initializeSession() {
        if (securePrefsManager.deviceToken == null) {
            sessionManager.updateState(VotingState.Unprovisioned)
            return
        }

        viewModelScope.launch {
            try {
                val sessionResponse = orchestratorClient.getCurrentSession()
                val activeRound = sessionResponse.activeVotingRound

                val initialState = when {
                    activeRound != null && activeRound.status in listOf("DRAFT", "VOTING_OPEN", "VOTING_CLOSED") -> {
                        VotingState.VotingRoundActive(
                            votingRoundId = activeRound.id,
                            title = activeRound.agendaItem.title,
                            summary = activeRound.agendaItem.summary ?: "",
                            stage = activeRound.stage,
                            specificReference = activeRound.specificReference,
                            allowsAbstentions = true, // Default; full data comes via WS
                            isNominal = activeRound.isNominal,
                            ephemeralPublicKey = sessionResponse.session.ephemeralPublicKey,
                            presidingOfficerId = sessionResponse.session.presidingOfficerId,
                            presidentVotesOrdinarily = activeRound.presidentVotesOrdinarily,
                            status = activeRound.status,
                            timeLimitSeconds = activeRound.timeLimitSeconds
                        )
                    }
                    activeRound != null && activeRound.status == "TIED" -> {
                        // Presidential identity comparison for tie-breaker routing
                        val presidingOfficerId = sessionResponse.session.presidingOfficerId
                        val localLegislatorId = securePrefsManager.legislatorId

                        if (localLegislatorId != null && localLegislatorId == presidingOfficerId) {
                            VotingState.TieBreakerActive(
                                votingRoundId = activeRound.id,
                                title = activeRound.agendaItem.title,
                                summary = activeRound.agendaItem.summary ?: "",
                                stage = activeRound.stage,
                                specificReference = activeRound.specificReference
                            )
                        } else {
                            VotingState.MotionTiedIdle
                        }
                    }
                    sessionResponse.activeAgendaItem != null && (sessionResponse.activeAgendaItem.status == "DEBATE" || sessionResponse.activeAgendaItem.status == "APPROVED_IN_GENERAL") -> {
                        VotingState.DebateIdle(
                            agendaItemId = sessionResponse.activeAgendaItem.id,
                            title = sessionResponse.activeAgendaItem.title,
                            summary = sessionResponse.activeAgendaItem.summary ?: ""
                        )
                    }
                    else -> VotingState.Idle
                }

                sessionManager.updateState(initialState)
                startKeepAliveService()
            } catch (e: Exception) {
                startKeepAliveService()
            }
        }
    }

    private fun startKeepAliveService() {
        val intent = Intent(context, SessionKeepAliveService::class.java)
        ContextCompat.startForegroundService(context, intent)
    }

    /**
     * Provisions the device by generating a Keystore key pair and enrolling via the REST API.
     */
    fun provisionDevice(nationalId: String, adminUsername: String, adminPassword: String) {
        viewModelScope.launch {
            try {
                // 1. Authenticate Admin (ephemeral session)
                orchestratorClient.adminLogin(LoginRequest(adminUsername, adminPassword))

                // 2. Generate hardware-bound key pair
                val certChain = keyStoreManager.generateKeyPairWithAttestation(nationalId)
                val enrollRequest = EnrollRequest(
                    nationalId = nationalId,
                    fullName = "Mock Legislator Name",
                    hardwareId = securePrefsManager.hardwareId,
                    biometricPayload = "MOCK_FACIAL_CAPTURE_BASE64",
                    certificateChain = certChain
                )

                // 3. Enroll via REST (admin cookie is sent automatically)
                val response = orchestratorClient.enrollLegislator(enrollRequest)
                securePrefsManager.deviceToken = response.device.deviceToken
                securePrefsManager.legislatorId = response.id

                sessionManager.updateState(VotingState.Idle)
                startKeepAliveService()
            } catch (e: Exception) {
                e.printStackTrace()
            } finally {
                // 4. ALWAYS destroy admin session
                orchestratorClient.adminLogout()
            }
        }
    }

    /**
     * Constructs the payload, prompts for biometric authentication, signs the payload,
     * and submits the vote to the REST API.
     */
    fun submitVote(activity: FragmentActivity, voteValue: String) {
        val currentState = uiState.value
        if (currentState !is VotingState.VotingRoundActive) return
        if (currentState.status != "VOTING_OPEN") return

        viewModelScope.launch {
            try {
                val timestamp = System.currentTimeMillis()
                val legislatorId = securePrefsManager.legislatorId
                    ?: throw IllegalStateException("Legislator ID missing")

                if (currentState.isNominal) {
                    val unsignedRequest = NominalVoteRequest(
                        motionId = currentState.votingRoundId,
                        legislatorId = legislatorId,
                        voteValue = voteValue,
                        timestamp = timestamp,
                        cryptographicSignature = "" // Placeholder for canonicalization
                    )
                    
                    val canonicalJson = PayloadCanonicalizer.buildNominalPayload(unsignedRequest)
                    val signature = biometricSigner.authenticateAndSign(activity, canonicalJson.toByteArray(Charsets.UTF_8))
                    
                    val signedRequest = unsignedRequest.copy(cryptographicSignature = signature)
                    orchestratorClient.castNominalVote(signedRequest)
                    
                } else {
                    val ephemeralPublicKey = currentState.ephemeralPublicKey
                        ?: throw IllegalStateException("Ephemeral public key missing for non-nominal vote")
                        
                    val receiptId = UUID.randomUUID().toString()
                    val innerEnvelope = buildJsonObject {
                        put("receipt_id", receiptId)
                        put("vote_value", voteValue)
                    }.toString()
                    
                    val encryptedPayload = encryptionUtils.encryptNonNominalPayload(innerEnvelope, ephemeralPublicKey)
                    
                    val unsignedRequest = NonNominalVoteRequest(
                        motionId = currentState.votingRoundId,
                        legislatorId = legislatorId,
                        encryptedPayload = encryptedPayload,
                        timestamp = timestamp,
                        cryptographicSignature = "" // Placeholder
                    )
                    
                    val canonicalJson = PayloadCanonicalizer.buildNonNominalPayload(unsignedRequest)
                    val signature = biometricSigner.authenticateAndSign(activity, canonicalJson.toByteArray(Charsets.UTF_8))
                    
                    val signedRequest = unsignedRequest.copy(cryptographicSignature = signature)
                    orchestratorClient.castNonNominalVote(signedRequest)
                }
                
                sessionManager.markVoteSubmitted()
                
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    /**
     * Submits a presidential tie-breaker vote for the currently tied voting round.
     *
     * Follows the identical cryptographic flow as a nominal [submitVote]:
     * canonicalize → biometric sign → POST. The only difference is the
     * endpoint ([OrchestratorClient.castTieBreakerVote]) and the state
     * transition ([VotingState.TieBreakerLocked]).
     *
     * @param activity The [FragmentActivity] required for the BiometricPrompt dialog.
     * @param voteValue The deciding vote: "AFFIRMATIVE" or "NEGATIVE" (no abstention on tie-break).
     */
    fun submitTieBreakerVote(activity: FragmentActivity, voteValue: String) {
        val currentState = uiState.value
        if (currentState !is VotingState.TieBreakerActive) return

        viewModelScope.launch {
            try {
                val timestamp = System.currentTimeMillis()
                val legislatorId = securePrefsManager.legislatorId
                    ?: throw IllegalStateException("Legislator ID missing")

                val unsignedRequest = NominalVoteRequest(
                    motionId = currentState.votingRoundId,
                    legislatorId = legislatorId,
                    voteValue = voteValue,
                    timestamp = timestamp,
                    cryptographicSignature = "" // Placeholder for canonicalization
                )

                val canonicalJson = PayloadCanonicalizer.buildNominalPayload(unsignedRequest)
                val signature = biometricSigner.authenticateAndSign(
                    activity,
                    canonicalJson.toByteArray(Charsets.UTF_8)
                )

                val signedRequest = unsignedRequest.copy(cryptographicSignature = signature)
                orchestratorClient.castTieBreakerVote(signedRequest)

                sessionManager.markTieBreakerSubmitted()

            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
