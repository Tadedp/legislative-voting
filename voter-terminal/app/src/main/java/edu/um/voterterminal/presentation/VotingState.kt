package edu.um.voterterminal.presentation

/**
 * Represents the distinct UI states of the Voter Terminal.
 */
sealed interface VotingState {
    /** The device has not yet been enrolled by an Administrator. */
    object Unprovisioned : VotingState

    /** The device is enrolled and connected, waiting for an active motion. */
    object Idle : VotingState

    /**
     * An active motion is available for voting.
     */
    data class VotingOpen(
        val motionId: String,
        val title: String,
        val summary: String,
        val allowsAbstentions: Boolean
    ) : VotingState

    /**
     * The user has successfully submitted a vote for the current motion.
     * The UI should visually lock and disable voting controls.
     */
    data class VoteLocked(
        val motionId: String
    ) : VotingState

    /**
     * A remote DEVICE_WIPE_COMMAND was received.
     * The terminal is dead and the UI must hard-lock.
     */
    object DeviceRevoked : VotingState
}
