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
    fun buildNominalPayload(request: NominalVoteRequest): String {
        // Build sorted manually or using a sorted map to ensure deterministic output
        val sortedMap = sortedMapOf(
            "action" to JsonPrimitive("nominal"),
            "legislator_id" to JsonPrimitive(request.legislatorId),
            "timestamp" to JsonPrimitive(request.timestamp),
            "vote_value" to JsonPrimitive(request.voteValue),
            "voting_round_id" to JsonPrimitive(request.votingRoundId)
        )
        val jsonObject = JsonObject(sortedMap)
        // Json.encodeToString on JsonObject with default configuration produces no whitespace
        return Json.encodeToString(jsonObject)
    }

    /**
     * Creates the canonical payload for a Non-Nominal Vote.
     * Only includes the fields that are actually signed (excludes the signature itself).
     */
    fun buildNonNominalPayload(request: NonNominalVoteRequest): String {
        val sortedMap = sortedMapOf(
            "action" to JsonPrimitive("non_nominal"),
            "legislator_id" to JsonPrimitive(request.legislatorId),
            "salt" to JsonPrimitive(request.salt),
            "timestamp" to JsonPrimitive(request.timestamp),
            "vote_value" to JsonPrimitive(request.voteValue),
            "voting_round_id" to JsonPrimitive(request.votingRoundId)
        )
        val jsonObject = JsonObject(sortedMap)
        return Json.encodeToString(jsonObject)
    }

    /**
     * Creates the canonical payload for a Tie Breaker Vote.
     */
    fun buildTieBreakerPayload(request: NominalVoteRequest): String {
        val sortedMap = sortedMapOf(
            "action" to JsonPrimitive("tie_breaker"),
            "legislator_id" to JsonPrimitive(request.legislatorId),
            "timestamp" to JsonPrimitive(request.timestamp),
            "vote_value" to JsonPrimitive(request.voteValue),
            "voting_round_id" to JsonPrimitive(request.votingRoundId)
        )
        val jsonObject = JsonObject(sortedMap)
        return Json.encodeToString(jsonObject)
    }
}
