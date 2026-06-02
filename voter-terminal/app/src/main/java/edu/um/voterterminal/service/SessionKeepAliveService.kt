package edu.um.voterterminal.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import dagger.hilt.android.AndroidEntryPoint
import edu.um.voterterminal.data.local.SecurePrefsManager
import edu.um.voterterminal.data.network.OrchestratorClient
import edu.um.voterterminal.data.network.OrchestratorEvent
import edu.um.voterterminal.domain.SessionManager
import edu.um.voterterminal.presentation.VotingState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

/**
 * Foreground Service responsible for maintaining the Ktor WebSocket connection
 * alive even when the app is backgrounded, mitigating Doze mode.
 *
 * Parses Orchestrator WebSocket events and transitions the UI state via
 * [SessionManager]. Event names follow the `VOTING_ROUND_*` convention
 * aligned with the Orchestrator's domain-separated architecture.
 */
@AndroidEntryPoint
class SessionKeepAliveService : Service() {

    @Inject
    lateinit var orchestratorClient: OrchestratorClient

    @Inject
    lateinit var sessionManager: SessionManager

    @Inject
    lateinit var securePrefsManager: SecurePrefsManager

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    companion object {
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "voter_terminal_session_channel"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = createNotification()
        
        // Android 14+ requires explicitly specifying foregroundServiceType in code if targeted
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        observeWebSocket()

        return START_STICKY
    }

    private fun observeWebSocket() {
        serviceScope.launch {
            orchestratorClient.observeState().collect { event ->
                when (event.eventType) {
                    OrchestratorEvent.VOTING_ROUND_OPENED -> {
                        val votingRoundId = event.data["voting_round_id"]?.jsonPrimitive?.content ?: ""
                        val stage = event.data["stage"]?.jsonPrimitive?.content ?: "SINGLE"
                        val specificReference = event.data["specific_reference"]?.jsonPrimitive?.content
                        val allowsAbstentions = event.data["allows_abstentions"]?.jsonPrimitive?.boolean ?: true
                        val isNominal = event.data["is_nominal"]?.jsonPrimitive?.boolean ?: true
                        val ephemeralPublicKey = event.data["ephemeral_public_key"]?.jsonPrimitive?.content
                        val presidingOfficerId = event.data["presiding_officer_id"]?.jsonPrimitive?.content
                        val presidentVotesOrdinarily = event.data["president_votes_ordinarily"]?.jsonPrimitive?.boolean ?: true

                        // Extract nested agenda_item context for display
                        val agendaItem = event.data["agenda_item"]?.jsonObject
                        val title = agendaItem?.get("title")?.jsonPrimitive?.content ?: "Unknown"
                        val summary = agendaItem?.get("summary")?.jsonPrimitive?.content ?: ""

                        sessionManager.updateState(
                            VotingState.VotingOpen(
                                votingRoundId = votingRoundId,
                                title = title,
                                summary = summary,
                                stage = stage,
                                specificReference = specificReference,
                                allowsAbstentions = allowsAbstentions,
                                isNominal = isNominal,
                                ephemeralPublicKey = ephemeralPublicKey,
                                presidingOfficerId = presidingOfficerId,
                                presidentVotesOrdinarily = presidentVotesOrdinarily
                            )
                        )
                    }
                    OrchestratorEvent.VOTING_ROUND_TIED -> {
                        val votingRoundId = event.data["voting_round_id"]?.jsonPrimitive?.content ?: ""
                        val presidingOfficerId = event.data["presiding_officer_id"]?.jsonPrimitive?.content
                        val legislatorId = securePrefsManager.legislatorId

                        // Extract stage context for badge rendering on the tie-breaker screen.
                        // The current VotingOpen state carries the original stage/reference;
                        // fall back to it if the TIED event doesn't include them.
                        val currentState = sessionManager.state.value
                        val stage = if (currentState is VotingState.VotingOpen) currentState.stage else "SINGLE"
                        val specificReference = if (currentState is VotingState.VotingOpen) currentState.specificReference else null
                        val title = if (currentState is VotingState.VotingOpen) currentState.title else "Unknown"
                        val summary = if (currentState is VotingState.VotingOpen) currentState.summary else ""

                        // Presidential identity comparison: route to the appropriate tie state
                        val tieState = if (legislatorId != null && legislatorId == presidingOfficerId) {
                            VotingState.TieBreakerActive(
                                votingRoundId = votingRoundId,
                                title = title,
                                summary = summary,
                                stage = stage,
                                specificReference = specificReference
                            )
                        } else {
                            VotingState.MotionTiedIdle
                        }
                        sessionManager.updateState(tieState)
                    }
                    OrchestratorEvent.VOTING_ROUND_CLOSED,
                    OrchestratorEvent.VOTING_ROUND_ABORTED,
                    OrchestratorEvent.VOTING_ROUND_RESOLVED -> {
                        // We do not blindly go to Idle because the AgendaItem might still be on the floor.
                        // For a robust reactive UI, we can just fetch the REST state, or let the Presidency
                        // trigger an AGENDA_ITEM_UPDATED if they change its status. For now, we fallback to Idle.
                        // A better approach would be to check if the item is still in DEBATE, but the event doesn't carry it.
                        sessionManager.updateState(VotingState.Idle)
                    }
                    OrchestratorEvent.AGENDA_ITEM_UPDATED -> {
                        val status = event.data["status"]?.jsonPrimitive?.content ?: ""
                        val currentState = sessionManager.state.value
                        
                        // We only transition if we are not currently in an active voting flow
                        val isVotingFlow = currentState is VotingState.VotingOpen || 
                                           currentState is VotingState.VoteLocked || 
                                           currentState is VotingState.TieBreakerActive || 
                                           currentState is VotingState.TieBreakerLocked ||
                                           currentState is VotingState.MotionTiedIdle
                        
                        if (!isVotingFlow) {
                            if (status == "DEBATE" || status == "APPROVED_IN_GENERAL") {
                                val agendaItemId = event.data["id"]?.jsonPrimitive?.content ?: ""
                                val title = event.data["title"]?.jsonPrimitive?.content ?: ""
                                val summary = event.data["summary"]?.jsonPrimitive?.content ?: ""
                                
                                sessionManager.updateState(
                                    VotingState.DebateIdle(
                                        agendaItemId = agendaItemId,
                                        title = title,
                                        summary = summary
                                    )
                                )
                            } else {
                                sessionManager.updateState(VotingState.Idle)
                            }
                        }
                    }
                    OrchestratorEvent.DEVICE_WIPE_COMMAND -> {
                        sessionManager.executeWipeProtocol()
                        stopSelf()
                    }
                }
            }
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Legislative Session",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Maintains a secure connection to the Orchestrator."
            }
            val notificationManager: NotificationManager =
                getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Legislative Terminal")
            .setContentText("Secure connection active")
            .setSmallIcon(android.R.drawable.ic_secure) // Generic icon for now
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null // We don't provide binding, just start/stop
    }
}
