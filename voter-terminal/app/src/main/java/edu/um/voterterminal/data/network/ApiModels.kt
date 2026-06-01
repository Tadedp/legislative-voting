package edu.um.voterterminal.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// ---------------------------------------------------------------------------
// Request Models
// ---------------------------------------------------------------------------

/**
 * POST /auth/login
 *
 * Ephemeral admin authentication used during device provisioning.
 * The session cookie is handled automatically by the Ktor HttpCookies plugin.
 */
@Serializable
data class LoginRequest(
    val username: String,
    val password: String
)

/**
 * POST /legislators/enroll
 *
 * Enrolls a legislator by submitting identity verification data and
 * the X.509 certificate chain from Android Key Attestation.
 */
@Serializable
data class EnrollRequest(
    @SerialName("national_id")
    val nationalId: String,

    @SerialName("hardware_id")
    val hardwareId: String,

    @SerialName("full_name")
    val fullName: String,

    @SerialName("biometric_payload")
    val biometricPayload: String,

    @SerialName("certificate_chain")
    val certificateChain: List<String>
)

/**
 * POST /votes/nominal
 *
 * Submits a plaintext signed vote for a nominal (roll-call) motion.
 * Auth is via cryptographic signature — no device token header.
 */
@Serializable
data class NominalVoteRequest(
    @SerialName("motion_id")
    val motionId: String,

    @SerialName("legislator_id")
    val legislatorId: String,

    @SerialName("vote_value")
    val voteValue: String,

    val timestamp: Long,

    @SerialName("cryptographic_signature")
    val cryptographicSignature: String
)

/**
 * POST /votes/non-nominal
 *
 * Submits a double-envelope encrypted vote for a non-nominal (secret) motion.
 * Auth is via cryptographic signature — no device token header.
 */
@Serializable
data class NonNominalVoteRequest(
    @SerialName("motion_id")
    val motionId: String,

    @SerialName("legislator_id")
    val legislatorId: String,

    @SerialName("encrypted_payload")
    val encryptedPayload: String,

    val timestamp: Long,

    @SerialName("cryptographic_signature")
    val cryptographicSignature: String
)

// ---------------------------------------------------------------------------
// Response Models
// ---------------------------------------------------------------------------

/**
 * Response from GET /legislative-sessions/current.
 * Wraps the authoritative session state and the currently open motion (if any).
 */
@Serializable
data class CurrentSessionResponse(
    val session: SessionInfo,
    @SerialName("active_motion")
    val activeMotion: ActiveMotionInfo? = null
)

@Serializable
data class SessionInfo(
    val id: String,
    val title: String,
    val status: String,
    @SerialName("ephemeral_public_key")
    val ephemeralPublicKey: String? = null,
    @SerialName("presiding_officer_id")
    val presidingOfficerId: String? = null,
    @SerialName("created_at")
    val createdAt: String? = null
)

@Serializable
data class ActiveMotionInfo(
    val id: String,
    val title: String,
    val summary: String? = null,
    @SerialName("is_nominal")
    val isNominal: Boolean,
    val status: String,
    @SerialName("presiding_officer_id")
    val presidingOfficerId: String? = null,
    @SerialName("president_votes_ordinarily")
    val presidentVotesOrdinarily: Boolean = true
)

/**
 * Nested device info returned within the enrollment response.
 */
@Serializable
data class DeviceInfo(
    val id: String,
    @SerialName("hardware_id")
    val hardwareId: String,
    @SerialName("device_token")
    val deviceToken: String
)

/**
 * Response from POST /legislators/enroll.
 * Contains the legislator identity and the provisioned device details.
 */
@Serializable
data class EnrollResponse(
    val id: String,
    @SerialName("national_id")
    val nationalId: String,
    val device: DeviceInfo
)

/**
 * Response from POST /votes/nominal and POST /votes/non-nominal.
 */
@Serializable
data class VoteResponse(
    @SerialName("event_id")
    val eventId: String,
    val status: String? = null
)

// ---------------------------------------------------------------------------
// WebSocket Event Models
// ---------------------------------------------------------------------------

/**
 * Generic event envelope received from the Orchestrator WebSocket at
 * `ws://<host>/ws/state?token=<device_token>`.
 *
 * The [data] field is a flexible [JsonObject] whose shape varies by [eventType].
 */
@Serializable
data class OrchestratorEvent(
    @SerialName("event_type")
    val eventType: String,

    val data: JsonObject
) {
    companion object {
        /** A motion is opened for voting. */
        const val MOTION_OPENED = "MOTION_OPENED"

        /** A motion is closed. */
        const val MOTION_CLOSED = "MOTION_CLOSED"

        /** A motion was aborted by the Presidency — clears vote lock-out. */
        const val MOTION_ABORTED = "MOTION_ABORTED"

        /** A motion resulted in a tie — triggers presidential tie-breaker flow. */
        const val MOTION_TIED = "MOTION_TIED"

        /** Remote device revocation — triggers local wipe protocol. */
        const val DEVICE_WIPE_COMMAND = "DEVICE_WIPE_COMMAND"
    }
}
