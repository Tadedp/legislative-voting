package edu.um.voterterminal.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages secure local storage using [EncryptedSharedPreferences].
 *
 * Responsibilities:
 * - Auto-generates and permanently stores a [hardwareId] (UUIDv4) on first initialization.
 * - Provides safe getter/setter for the Orchestrator-issued [deviceToken].
 * - Supports full wipe via [clearAll] for the Device Wipe Protocol.
 *
 * Encryption:
 * - Key scheme: AES256_SIV (deterministic AEAD for key encryption)
 * - Value scheme: AES256_GCM (randomized AEAD for value encryption)
 */
@Singleton
class SecurePrefsManager @Inject constructor(
    @ApplicationContext context: Context
) {
    private companion object {
        const val PREFS_FILENAME = "voter_terminal_secure_prefs"
        const val KEY_HARDWARE_ID = "hardware_id"
        const val KEY_DEVICE_TOKEN = "device_token"
    }

    private val masterKeyAlias: String = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)

    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        PREFS_FILENAME,
        masterKeyAlias,
        context,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    init {
        // Generate and persist hardware_id on first-ever initialization.
        // This value is immutable once written — it anchors the device identity.
        if (!prefs.contains(KEY_HARDWARE_ID)) {
            prefs.edit()
                .putString(KEY_HARDWARE_ID, UUID.randomUUID().toString())
                .apply()
        }
    }

    /**
     * The device's permanent hardware identifier (UUIDv4).
     * Generated once on first launch and never changes.
     */
    val hardwareId: String
        get() = prefs.getString(KEY_HARDWARE_ID, null)
            ?: throw IllegalStateException("hardware_id must exist after initialization")

    /**
     * The Orchestrator-issued device token, or `null` if the device is not yet enrolled.
     */
    var deviceToken: String?
        get() = prefs.getString(KEY_DEVICE_TOKEN, null)
        set(value) {
            prefs.edit()
                .putString(KEY_DEVICE_TOKEN, value)
                .apply()
        }

    /**
     * Wipes all secure storage. Used by the Device Wipe Protocol
     * when a `DEVICE_WIPE_COMMAND` is received from the Orchestrator.
     */
    fun clearAll() {
        prefs.edit().clear().apply()
    }
}
