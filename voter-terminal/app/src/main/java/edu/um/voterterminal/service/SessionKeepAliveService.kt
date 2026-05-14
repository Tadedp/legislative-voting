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
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

/**
 * Foreground Service responsible for maintaining the Ktor WebSocket connection
 * alive even when the app is backgrounded, mitigating Doze mode.
 */
@AndroidEntryPoint
class SessionKeepAliveService : Service() {

    @Inject
    lateinit var orchestratorClient: OrchestratorClient

    @Inject
    lateinit var sessionManager: SessionManager

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
                    OrchestratorEvent.MOTION_OPENED -> {
                        val motionId = event.data["motion_id"]?.jsonPrimitive?.content ?: ""
                        val title = event.data["title"]?.jsonPrimitive?.content ?: "Unknown Motion"
                        val summary = event.data["summary"]?.jsonPrimitive?.content ?: ""
                        val allowsAbstentions = event.data["allows_abstentions"]?.jsonPrimitive?.boolean ?: true

                        sessionManager.updateState(
                            VotingState.VotingOpen(
                                motionId = motionId,
                                title = title,
                                summary = summary,
                                allowsAbstentions = allowsAbstentions
                            )
                        )
                    }
                    OrchestratorEvent.MOTION_CLOSED,
                    OrchestratorEvent.MOTION_ABORTED -> {
                        sessionManager.updateState(VotingState.Idle)
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
