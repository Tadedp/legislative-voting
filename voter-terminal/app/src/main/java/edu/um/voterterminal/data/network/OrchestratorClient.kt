package edu.um.voterterminal.data.network

import edu.um.voterterminal.BuildConfig
import edu.um.voterterminal.data.local.SecurePrefsManager
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.plugins.websocket.webSocket
import io.ktor.client.plugins.cookies.HttpCookies
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.http.isSuccess
import io.ktor.websocket.Frame
import io.ktor.websocket.readText
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.isActive
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.min

/**
 * Ktor-based client for all communication with the Orchestrator API.
 *
 * REST endpoints use suspend functions. The WebSocket state stream is
 * exposed as a cold [Flow] with automatic reconnection and exponential backoff.
 *
 * Auth rules (per Orchestrator contract):
 * - `GET /sessions/current`: `X-Device-Token` custom header
 * - `POST /legislators/enroll`: No auth header (device not yet provisioned)
 * - `POST /votes/nominal`, `POST /votes/non-nominal`: No auth header
 *   (Cryptographic Payload Authorization via signed payload)
 * - WebSocket `/ws/state`: `token` query parameter
 */
@Singleton
class OrchestratorClient @Inject constructor(
    private val httpClient: HttpClient,
    private val prefsManager: SecurePrefsManager
) {
    private companion object {
        const val HEADER_DEVICE_TOKEN = "X-Device-Token"
        const val BASE_RECONNECT_DELAY_MS = 1_000L
        const val MAX_RECONNECT_DELAY_MS = 30_000L
    }

    private val httpBaseUrl: String = BuildConfig.ORCHESTRATOR_HTTP_URL
    private val wsBaseUrl: String = BuildConfig.ORCHESTRATOR_WS_URL

    private val json = Json { ignoreUnknownKeys = true }
    
    private var ephemeralSessionCookie: String? = null

    // -----------------------------------------------------------------------
    // REST: Session
    // -----------------------------------------------------------------------

    /**
     * Fetches the current authoritative session state from the Orchestrator.
     * Used for resynchronization after WS drops or app backgrounding.
     *
     * Requires: enrolled device with a valid `device_token`.
     */
    suspend fun getCurrentSession(): CurrentSessionResponse {
        val response = httpClient.get("$httpBaseUrl/legislative-sessions/current") {
            header(HEADER_DEVICE_TOKEN, requireDeviceToken())
        }
        if (!response.status.isSuccess()) {
            throw IllegalStateException("API Error [${response.status.value}]: ${response.status.description}")
        }
        return response.body()
    }

    // -----------------------------------------------------------------------
    // REST: Enrollment
    // -----------------------------------------------------------------------

    /**
     * Enrolls a legislator by submitting RENAPER identity data and the
     * X.509 certificate chain from Android Key Attestation.
     *
     * No auth header — the device is not yet provisioned at this point.
     */
    suspend fun enrollLegislator(request: EnrollRequest): EnrollResponse {
        val response = httpClient.post("$httpBaseUrl/legislators/enroll") {
            contentType(ContentType.Application.Json)
            setBody(request)
            ephemeralSessionCookie?.let { cookieVal ->
                header("Cookie", cookieVal)
            }
        }
        if (!response.status.isSuccess()) {
            throw IllegalStateException("API Error [${response.status.value}]: ${response.status.description}")
        }
        return response.body()
    }

    // -----------------------------------------------------------------------
    // REST: Ephemeral Admin Authentication (for Provisioning)
    // -----------------------------------------------------------------------

    /**
     * Authenticates a system administrator via username/password.
     * The Ktor [HttpCookies] plugin automatically stores the `HttpOnly`
     * session cookie returned by the Orchestrator, so subsequent requests
     * (e.g. [enrollLegislator]) are transparently authenticated.
     *
     * This session is **ephemeral** — [adminLogout] MUST be called after
     * provisioning completes (or fails) to destroy the server-side session.
     */
    suspend fun adminLogin(request: LoginRequest) {
        val response = httpClient.post("$httpBaseUrl/auth/login") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }
        val setCookieHeader = response.headers["Set-Cookie"]
        if (setCookieHeader != null) {
            ephemeralSessionCookie = setCookieHeader.substringBefore(";")
        }
    }

    /**
     * Destroys the admin session on the Orchestrator and clears the
     * in-memory cookie storage to prevent accidental session reuse.
     */
    suspend fun adminLogout() {
        try {
            httpClient.post("$httpBaseUrl/auth/logout") {
                ephemeralSessionCookie?.let { cookieVal ->
                    header("Cookie", cookieVal)
                }
            }
        } catch (_: Exception) {
            // Best-effort: session may already be expired
        } finally {
            ephemeralSessionCookie = null
        }
    }

    // -----------------------------------------------------------------------
    // REST: Voting (Cryptographic Payload Authorization — NO auth headers)
    // -----------------------------------------------------------------------

    /**
     * Submits a nominal (roll-call) vote with a plaintext signed payload.
     * Auth is exclusively via the cryptographic signature in the request body.
     */
    suspend fun castNominalVote(request: NominalVoteRequest): VoteResponse {
        val response = httpClient.post("$httpBaseUrl/votes/nominal") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }
        if (!response.status.isSuccess()) {
            throw IllegalStateException("API Error [${response.status.value}]: ${response.status.description}")
        }
        return response.body()
    }

    /**
     * Submits a non-nominal (secret) vote with double-envelope encryption.
     * Auth is exclusively via the cryptographic signature in the request body.
     */
    suspend fun castNonNominalVote(request: NonNominalVoteRequest): VoteResponse {
        val response = httpClient.post("$httpBaseUrl/votes/non-nominal") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }
        if (!response.status.isSuccess()) {
            throw IllegalStateException("API Error [${response.status.value}]: ${response.status.description}")
        }
        return response.body()
    }

    // -----------------------------------------------------------------------
    // WebSocket: State Stream
    // -----------------------------------------------------------------------

    /**
     * Connects to the Orchestrator's WebSocket at `/ws/state` and emits
     * deserialized [OrchestratorEvent] objects as a cold [Flow].
     *
     * Automatically reconnects on disconnect with exponential backoff
     * (1s → 2s → 4s → ... → 30s cap) and jitter. Collection is infinite
     * until the collector cancels.
     *
     * Auth: `device_token` is sent as a query parameter per the
     * Orchestrator's `websocket_router.py` contract.
     */
    fun observeState(): Flow<OrchestratorEvent> = callbackFlow {
        var retryCount = 0

        while (isActive) {
            try {
                val token = requireDeviceToken()

                httpClient.webSocket(
                    urlString = "$wsBaseUrl/ws/state?device_token=$token"
                ) {
                    // Successful connection — reset backoff
                    retryCount = 0

                    for (frame in incoming) {
                        if (frame is Frame.Text) {
                            val text = frame.readText()
                            val event = json.decodeFromString<OrchestratorEvent>(text)
                            trySend(event)
                        }
                    }
                }
            } catch (e: Exception) {
                // Emit the error downstream without killing the Flow.
                // The collector decides whether to continue or cancel.
                if (!isActive) break

                // Exponential backoff with jitter
                val baseDelay = BASE_RECONNECT_DELAY_MS * (1L shl min(retryCount, 4))
                val cappedDelay = min(baseDelay, MAX_RECONNECT_DELAY_MS)
                val jitter = (0..(cappedDelay / 4)).random()
                delay(cappedDelay + jitter)
                retryCount++
            }
        }

        awaitClose {
            // Cleanup if needed when the collector cancels
        }
    }

    // -----------------------------------------------------------------------
    // Internal
    // -----------------------------------------------------------------------

    private fun requireDeviceToken(): String {
        return prefsManager.deviceToken
            ?: throw IllegalStateException(
                "device_token is not available. Device must be enrolled first."
            )
    }
}
