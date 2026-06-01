package edu.um.voterterminal.presentation

/**
 * Represents the distinct UI states of the Voter Terminal.
 *
 * Each state maps directly to a distinct Compose screen rendered by the
 * [Crossfade] router in [MainActivity]. Transitions are driven by the
 * [SessionManager] in response to Orchestrator WebSocket events and REST
 * hydration, ensuring Unidirectional Data Flow (UDF).
 */
sealed interface VotingState {
    /** The device has not yet been enrolled by an Administrator. */
    object Unprovisioned : VotingState

    /** The device is enrolled and connected, waiting for an active motion. */
    object Idle : VotingState

    /**
     * An active motion is available for voting.
     *
     * @property motionId Unique identifier of the open motion (UUIDv7).
     * @property title Short title of the motion being voted on.
     * @property summary Extended description of the motion.
     * @property allowsAbstentions Whether abstention is a valid vote option.
     * @property isNominal True for roll-call (public), false for secret ballot.
     * @property ephemeralPublicKey RSA public key for client-side encryption (non-nominal only).
     * @property presidingOfficerId The session's presiding officer ID, used for UI forking.
     * @property presidentVotesOrdinarily Whether the president must cast an ordinary vote.
     */
    data class VotingOpen(
        val motionId: String,
        val title: String,
        val summary: String,
        val allowsAbstentions: Boolean,
        val isNominal: Boolean,
        val ephemeralPublicKey: String? = null,
        val presidingOfficerId: String? = null,
        val presidentVotesOrdinarily: Boolean = true
    ) : VotingState

    /**
     * The user has successfully submitted a vote for the current motion.
     * The UI should visually lock and disable voting controls, while retaining context.
     */
    data class VoteLocked(
        val originalState: VotingOpen
    ) : VotingState

    /**
     * The motion resulted in a tie. Displayed to standard legislators (non-presidents)
     * while awaiting the presiding officer's deciding vote.
     */
    object MotionTiedIdle : VotingState

    /**
     * Exclusive state for the presiding officer when a motion results in a tie.
     * The UI presents a visually distinct (Gold/Purple) interface for the deciding vote.
     *
     * @property motionId The tied motion's UUIDv7 identifier.
     * @property title Short title of the tied motion.
     * @property summary Extended description of the tied motion.
     */
    data class TieBreakerActive(
        val motionId: String,
        val title: String,
        val summary: String
    ) : VotingState

    /**
     * The presiding officer has submitted their tie-breaker vote.
     * The UI remains on the distinct Gold/Purple tie-breaker screen,
     * visually dimmed with a success overlay, until the motion closes.
     */
    data class TieBreakerLocked(
        val originalState: TieBreakerActive
    ) : VotingState

    /**
     * A remote DEVICE_WIPE_COMMAND was received.
     * The terminal is dead and the UI must hard-lock.
     */
    object DeviceRevoked : VotingState
}
