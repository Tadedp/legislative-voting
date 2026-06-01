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

    init {
        initializeSession()
    }

    /**
     * Hydrates the terminal state from the Orchestrator REST API.
     *
     * Handles three motion scenarios:
     * - `VOTING_OPEN`: Rebuilds [VotingState.VotingOpen] with presidential fields.
     * - `TIED`: Performs presidential identity comparison and transitions to
     *   [VotingState.TieBreakerActive] or [VotingState.MotionTiedIdle].
     * - No active motion / other status: Transitions to [VotingState.Idle].
     */
    private fun initializeSession() {
        if (securePrefsManager.deviceToken == null) {
            sessionManager.updateState(VotingState.Unprovisioned)
            return
        }

        viewModelScope.launch {
            try {
                val sessionResponse = orchestratorClient.getCurrentSession()
                val activeMotion = sessionResponse.activeMotion

                val initialState = when {
                    activeMotion != null && activeMotion.status == "VOTING_OPEN" -> {
                        VotingState.VotingOpen(
                            motionId = activeMotion.id,
                            title = activeMotion.title,
                            summary = activeMotion.summary ?: "",
                            allowsAbstentions = true, // Default; full data comes via WS
                            isNominal = activeMotion.isNominal,
                            ephemeralPublicKey = sessionResponse.session.ephemeralPublicKey,
                            presidingOfficerId = activeMotion.presidingOfficerId
                                ?: sessionResponse.session.presidingOfficerId,
                            presidentVotesOrdinarily = activeMotion.presidentVotesOrdinarily
                        )
                    }
                    activeMotion != null && activeMotion.status == "TIED" -> {
                        // Presidential identity comparison for tie-breaker routing
                        val presidingOfficerId = activeMotion.presidingOfficerId
                            ?: sessionResponse.session.presidingOfficerId
                        val localLegislatorId = securePrefsManager.legislatorId

                        if (localLegislatorId != null && localLegislatorId == presidingOfficerId) {
                            VotingState.TieBreakerActive(
                                motionId = activeMotion.id,
                                title = activeMotion.title,
                                summary = activeMotion.summary ?: ""
                            )
                        } else {
                            VotingState.MotionTiedIdle
                        }
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
        if (currentState !is VotingState.VotingOpen) return

        viewModelScope.launch {
            try {
                val timestamp = System.currentTimeMillis()
                val legislatorId = securePrefsManager.legislatorId
                    ?: throw IllegalStateException("Legislator ID missing")

                if (currentState.isNominal) {
                    val unsignedRequest = NominalVoteRequest(
                        motionId = currentState.motionId,
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
                        motionId = currentState.motionId,
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
     * Submits a presidential tie-breaker vote for the currently tied motion.
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
                    motionId = currentState.motionId,
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
