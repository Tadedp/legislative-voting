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

    /** Terminal is enrolled and connected, but no motion is currently active or on the floor. */
    object Idle : VotingState

    /** 
     * An agenda item is currently being debated (on the floor), but no voting round 
     * is currently open. The UI should display the item's context without voting controls.
     */
    data class DebateIdle(
        val agendaItemId: String,
        val title: String,
        val summary: String
    ) : VotingState

    /**
     * An active voting round is available for voting.
     *
     * @property votingRoundId Unique identifier of the open voting round (UUIDv7).
     * @property title Short title of the parent agenda item.
     * @property summary Extended description of the parent agenda item.
     * @property stage The round stage: "SINGLE", "GENERAL", or "SPECIFIC".
     * @property specificReference Human-readable reference for SPECIFIC rounds
     *   (e.g., "Artículo 4"). Null for SINGLE and GENERAL rounds.
     * @property allowsAbstentions Whether abstention is a valid vote option.
     * @property isNominal True for roll-call (public), false for secret ballot.
     * @property ephemeralPublicKey RSA public key for client-side encryption (non-nominal only).
     * @property presidingOfficerId The session's presiding officer ID, used for UI forking.
     * @property presidentVotesOrdinarily Whether the president must cast an ordinary vote.
     * @property status Tracks DRAFT, VOTING_OPEN, or VOTING_CLOSED.
     * @property timeLimitSeconds Optional countdown timer length.
     */
    data class VotingRoundActive(
        val votingRoundId: String,
        val title: String,
        val summary: String,
        val stage: String = "SINGLE",
        val specificReference: String? = null,
        val allowsAbstentions: Boolean,
        val isNominal: Boolean,
        val ephemeralPublicKey: String? = null,
        val presidingOfficerId: String? = null,
        val presidentVotesOrdinarily: Boolean = true,
        val status: String,
        val timeLimitSeconds: Int? = null
    ) : VotingState

    /**
     * The user has successfully submitted a vote for the current round.
     * The UI should visually lock and disable voting controls, while retaining context.
     */
    data class VoteLocked(
        val originalState: VotingRoundActive
    ) : VotingState

    /**
     * The voting round resulted in a tie. Displayed to standard legislators
     * (non-presidents) while awaiting the presiding officer's deciding vote.
     */
    object MotionTiedIdle : VotingState

    /**
     * Exclusive state for the presiding officer when a voting round results
     * in a tie. The UI presents a visually distinct (Gold/Purple) interface
     * for the deciding vote.
     *
     * @property votingRoundId The tied voting round's UUIDv7 identifier.
     * @property title Short title of the parent agenda item.
     * @property summary Extended description of the parent agenda item.
     * @property stage The round stage for badge rendering.
     * @property specificReference Human-readable reference for SPECIFIC rounds.
     */
    data class TieBreakerActive(
        val votingRoundId: String,
        val title: String,
        val summary: String,
        val stage: String = "SINGLE",
        val specificReference: String? = null
    ) : VotingState

    /**
     * The presiding officer has submitted their tie-breaker vote.
     * The UI remains on the distinct Gold/Purple tie-breaker screen,
     * visually dimmed with a success overlay, until the round closes.
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
