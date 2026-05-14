package edu.um.voterterminal.di

import android.content.Context
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import edu.um.voterterminal.data.local.SecurePrefsManager
import edu.um.voterterminal.data.network.OrchestratorClient
import io.ktor.client.HttpClient
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.websocket.WebSockets
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import javax.inject.Singleton

/**
 * Hilt module providing application-scoped singletons for
 * secure storage, networking, and the Orchestrator client.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideSecurePrefsManager(
        @ApplicationContext context: Context
    ): SecurePrefsManager {
        return SecurePrefsManager(context)
    }

    @Provides
    @Singleton
    fun provideHttpClient(): HttpClient {
        return HttpClient(CIO) {
            install(ContentNegotiation) {
                json(Json {
                    ignoreUnknownKeys = true
                    encodeDefaults = true
                    isLenient = true
                })
            }
            install(WebSockets)
        }
    }

    @Provides
    @Singleton
    fun provideOrchestratorClient(
        httpClient: HttpClient,
        prefsManager: SecurePrefsManager
    ): OrchestratorClient {
        return OrchestratorClient(httpClient, prefsManager)
    }
}
