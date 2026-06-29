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
import edu.um.voterterminal.data.network.DeviceEnrollRequest
import edu.um.voterterminal.data.network.NominalVoteRequest
import edu.um.voterterminal.data.network.NonNominalVoteRequest
import edu.um.voterterminal.data.network.OrchestratorClient
import edu.um.voterterminal.domain.SessionManager
import edu.um.voterterminal.R
import edu.um.voterterminal.security.BiometricSigner
import edu.um.voterterminal.security.EncryptionUtils
import edu.um.voterterminal.security.KeyStoreManager
import edu.um.voterterminal.security.CryptoUtils
import edu.um.voterterminal.security.PayloadCanonicalizer
import edu.um.voterterminal.service.SessionKeepAliveService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.security.MessageDigest
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

    private val _provisioningError = MutableStateFlow<String?>(null)
    val provisioningError: StateFlow<String?> = _provisioningError

    private var volatileSaltArray: CharArray? = null
    
    private val _volatileSaltString = MutableStateFlow<String?>(null)
    val volatileSaltString: StateFlow<String?> = _volatileSaltString.asStateFlow()

    private var timerJob: kotlinx.coroutines.Job? = null

    /**
     * Wipes the authoritative salt array from RAM using '0' fills
     * before garbage collecting, preventing memory dump attacks.
     */
    fun wipeVolatileSalt() {
        volatileSaltArray?.fill('0')
        volatileSaltArray = null
        _volatileSaltString.value = null
        System.gc()
    }

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
                
                // Coercion Defense: Wipe the volatile salt if the active round closes
                // or if we transition to any state other than the open round.
                val isVotingOpen = (state is VotingState.VotingRoundActive && state.status == "VOTING_OPEN") ||
                                   (state is VotingState.VoteLocked && state.originalState.status == "VOTING_OPEN")
                
                if (!isVotingOpen) {
                    wipeVolatileSalt()
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

    fun clearProvisioningError() {
        _provisioningError.value = null
    }

    /**
     * Provisions the device by generating a Keystore key pair and enrolling via the REST API.
     */
    fun provisionDevice(provisioningToken: String, biometricPayload: String) {
        viewModelScope.launch {
            try {
                _provisioningError.value = null

                // 1. Generate hardware-bound key pair, passing OTPT as challenge
                val certChain = keyStoreManager.generateKeyPairWithAttestation(provisioningToken)
                
                // 2. Compute hardware fingerprint (SHA-256 of the DER encoded public key inside the cert)
                // Note: The KeyStoreManager returns Base64 encoded DER certificates.
                val certBytes = android.util.Base64.decode(certChain[0], android.util.Base64.DEFAULT)
                val factory = java.security.cert.CertificateFactory.getInstance("X.509")
                val cert = factory.generateCertificate(java.io.ByteArrayInputStream(certBytes)) as java.security.cert.X509Certificate
                val pubKeyBytes = cert.publicKey.encoded // SubjectPublicKeyInfo in DER
                val digest = MessageDigest.getInstance("SHA-256")
                val hashBytes = digest.digest(pubKeyBytes)
                val hardwareFingerprint = hashBytes.joinToString("") { "%02x".format(it) }

                val enrollRequest = DeviceEnrollRequest(
                    provisioningToken = provisioningToken.trim(),
                    biometricPayload = biometricPayload,
                    hardwareFingerprint = hardwareFingerprint,
                    certificateChain = certChain
                )

                // 3. Enroll via REST
                val response = orchestratorClient.enrollDevice(enrollRequest)
                securePrefsManager.deviceToken = response.deviceToken
                securePrefsManager.legislatorId = response.legislatorId

                sessionManager.updateState(VotingState.Idle)
                startKeepAliveService()
            } catch (e: IllegalStateException) {
                if (e.message == "HTTP 403") {
                    _provisioningError.value = context.getString(R.string.identity_verification_failed)
                } else {
                    _provisioningError.value = e.message
                    e.printStackTrace()
                }
            } catch (e: Exception) {
                _provisioningError.value = e.message
                e.printStackTrace()
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
                    val canonicalJson = PayloadCanonicalizer.buildNominalPayload(
                        votingRoundId = currentState.votingRoundId,
                        legislatorId = legislatorId,
                        voteValue = voteValue,
                        timestamp = timestamp
                    )
                    
                    val signature = biometricSigner.authenticateAndSign(
                        activity,
                        canonicalJson.toByteArray(Charsets.UTF_8),
                        voteValue,
                        currentState.specificReference ?: ""
                    )
                    
                    val signedRequest = NominalVoteRequest(
                        rawPayloadString = canonicalJson,
                        cryptographicSignature = signature
                    )
                    orchestratorClient.castNominalVote(signedRequest)
                    
                } else {
                    val ephemeralPublicKey = currentState.ephemeralPublicKey
                        ?: throw IllegalStateException("Ephemeral public key missing for non-nominal vote")
                    // 1. Generate the authoritative secure salt
                    val saltArray = CryptoUtils.generateVolatileSalt()
                    volatileSaltArray = saltArray
                    
                    // 2. Derive the string for UI display and payload
                    val saltString = String(saltArray)
                    _volatileSaltString.value = saltString
                    
                    val canonicalJson = PayloadCanonicalizer.buildNonNominalPayload(
                        votingRoundId = currentState.votingRoundId,
                        legislatorId = legislatorId,
                        voteValue = voteValue,
                        salt = saltString,
                        timestamp = timestamp
                    )

                    val signature = biometricSigner.authenticateAndSign(
                        activity,
                        canonicalJson.toByteArray(Charsets.UTF_8),
                        voteValue,
                        currentState.specificReference ?: ""
                    )
                    
                    val signedRequest = NonNominalVoteRequest(
                        rawPayloadString = canonicalJson,
                        cryptographicSignature = signature
                    )
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

                val canonicalJson = PayloadCanonicalizer.buildTieBreakerPayload(
                    votingRoundId = currentState.votingRoundId,
                    legislatorId = legislatorId,
                    voteValue = voteValue,
                    timestamp = timestamp
                )

                val signature = biometricSigner.authenticateAndSign(
                    activity,
                    canonicalJson.toByteArray(Charsets.UTF_8),
                    voteValue,
                    currentState.specificReference ?: ""
                )

                val signedRequest = NominalVoteRequest(
                    rawPayloadString = canonicalJson,
                    cryptographicSignature = signature
                )
                orchestratorClient.castTieBreakerVote(signedRequest)

                sessionManager.markTieBreakerSubmitted()

            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
