package edu.um.voterterminal.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// ---------------------------------------------------------------------------
// Request Models
// ---------------------------------------------------------------------------

/**
 * POST /devices/enroll
 *
 * Enrolls a device using a provisioning token, biometric verification,
 * and cryptographic attestation. No auth header required.
 */
@Serializable
data class DeviceEnrollRequest(
    @SerialName("provisioning_token")
    val provisioningToken: String,

    @SerialName("biometric_payload")
    val biometricPayload: String,

    @SerialName("hardware_fingerprint")
    val hardwareFingerprint: String,

    @SerialName("certificate_chain")
    val certificateChain: List<String>
)

/**
 * POST /votes/nominal
 *
 * Submits a plaintext signed vote for a nominal (roll-call) voting round.
 * Auth is via cryptographic signature — no device token header.
 *
 * Submits a plaintext signed vote for a nominal (roll-call) voting round.
 * Auth is via cryptographic signature — no device token header.
 */
@Serializable
data class NominalVoteRequest(
    @SerialName("raw_payload_string")
    val rawPayloadString: String,

    @SerialName("cryptographic_signature")
    val cryptographicSignature: String
)

/**
 * POST /votes/non-nominal
 *
 * Submits a double-envelope encrypted vote for a non-nominal (secret) round.
 * Auth is via cryptographic signature — no device token header.
 */
@Serializable
data class NonNominalVoteRequest(
    @SerialName("raw_payload_string")
    val rawPayloadString: String,
    @SerialName("cryptographic_signature")
    val cryptographicSignature: String
)

@Serializable
data class TieBreakerVoteRequest(
    @SerialName("raw_payload_string")
    val rawPayloadString: String,
    @SerialName("cryptographic_signature")
    val cryptographicSignature: String
)

// ---------------------------------------------------------------------------
// Response Models
// ---------------------------------------------------------------------------

/**
 * Response from GET /legislative-sessions/current.
 * Wraps the authoritative session state and the currently open voting round
 * (if any), enriched with its parent agenda item.
 */
@Serializable
data class CurrentSessionResponse(
    val session: SessionInfo,
    @SerialName("active_voting_round")
    val activeVotingRound: ActiveVotingRoundInfo? = null,
    @SerialName("active_agenda_item")
    val activeAgendaItem: AgendaItemInfo? = null
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

/**
 * Nested DTO returned inside [CurrentSessionResponse].
 * Represents a [VotingRound] enriched with its parent [AgendaItemInfo].
 */
@Serializable
data class ActiveVotingRoundInfo(
    val id: String,
    @SerialName("agenda_item_id")
    val agendaItemId: String,
    @SerialName("legislative_session_id")
    val legislativeSessionId: String,
    val stage: String,
    @SerialName("specific_reference")
    val specificReference: String? = null,
    @SerialName("is_nominal")
    val isNominal: Boolean,
    val status: String,
    @SerialName("president_votes_ordinarily")
    val presidentVotesOrdinarily: Boolean = true,
    @SerialName("time_limit_seconds")
    val timeLimitSeconds: Int? = null,
    @SerialName("agenda_item")
    val agendaItem: AgendaItemInfo
)

/**
 * Lightweight representation of an AgendaItem, nested inside
 * [ActiveVotingRoundInfo] for context rendering on the terminal.
 */
@Serializable
data class AgendaItemInfo(
    val id: String,
    val title: String,
    val summary: String? = null,
    val category: String? = null,
    val status: String? = null
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
 * Response from POST /devices/enroll.
 * Contains the enrolled legislator ID and device token.
 */
@Serializable
data class DeviceEnrollResponse(
    @SerialName("device_token")
    val deviceToken: String,
    @SerialName("device_id")
    val deviceId: String,
    @SerialName("legislator_id")
    val legislatorId: String
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
        /** A voting round is opened for voting. */
        const val VOTING_ROUND_OPENED = "VOTING_ROUND_OPENED"

        /** A voting round is closed. */
        const val VOTING_ROUND_CLOSED = "VOTING_ROUND_CLOSED"

        /** A voting round was aborted by the Presidency — clears vote lock-out. */
        const val VOTING_ROUND_ABORTED = "VOTING_ROUND_ABORTED"

        /** A voting round resulted in a tie — triggers presidential tie-breaker flow. */
        const val VOTING_ROUND_TIED = "VOTING_ROUND_TIED"

        /** A voting round was resolved (PASSED/FAILED) — clears to idle. */
        const val VOTING_ROUND_RESOLVED = "VOTING_ROUND_RESOLVED"

        /** Remote device revocation — triggers local wipe protocol. */
        const val DEVICE_WIPE_COMMAND = "DEVICE_WIPE_COMMAND"

        /** An agenda item was updated (e.g., put on the floor for debate). */
        const val AGENDA_ITEM_UPDATED = "AGENDA_ITEM_UPDATED"
    }
}
