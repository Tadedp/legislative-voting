package edu.um.voterterminal.security

import edu.um.voterterminal.data.network.NominalVoteRequest
import edu.um.voterterminal.data.network.NonNominalVoteRequest
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * Utility to generate deterministic, canonical JSON strings for cryptographic signing.
 *
 * Requirements (matching Orchestrator verification):
 * - Keys must be sorted alphabetically.
 * - No whitespace (spaces or newlines) between keys and values.
 */
object PayloadCanonicalizer {

    /**
     * Creates the canonical payload for a Nominal Vote.
     * Only includes the fields that are actually signed (excludes the signature itself).
     */
    fun buildNominalPayload(votingRoundId: String, legislatorId: String, voteValue: String, timestamp: Long): String {
        // Build sorted manually or using a sorted map to ensure deterministic output
        val sortedMap = sortedMapOf(
            "legislator_id" to JsonPrimitive(legislatorId),
            "timestamp" to JsonPrimitive(timestamp),
            "vote_value" to JsonPrimitive(voteValue),
            "voting_round_id" to JsonPrimitive(votingRoundId)
        )
        val jsonObject = JsonObject(sortedMap)
        // Json.encodeToString on JsonObject with default configuration produces no whitespace
        return Json.encodeToString(jsonObject)
    }

    /**
     * Creates the canonical payload for a Non-Nominal Vote (Eligibility Payload).
     * Only includes identity and timing details. The actual vote intent is completely decoupled.
     */
    fun buildNonNominalEligibilityPayload(votingRoundId: String, legislatorId: String, timestamp: Long): String {
        val sortedMap = sortedMapOf(
            "legislator_id" to JsonPrimitive(legislatorId),
            "timestamp" to JsonPrimitive(timestamp),
            "voting_round_id" to JsonPrimitive(votingRoundId)
        )
        val jsonObject = JsonObject(sortedMap)
        return Json.encodeToString(jsonObject)
    }

    /**
     * Creates the canonical payload for a Tie Breaker Vote.
     */
    fun buildTieBreakerPayload(votingRoundId: String, legislatorId: String, voteValue: String, timestamp: Long): String {
        val sortedMap = sortedMapOf(
            "legislator_id" to JsonPrimitive(legislatorId),
            "timestamp" to JsonPrimitive(timestamp),
            "vote_value" to JsonPrimitive(voteValue),
            "voting_round_id" to JsonPrimitive(votingRoundId)
        )
        val jsonObject = JsonObject(sortedMap)
        return Json.encodeToString(jsonObject)
    }
}
