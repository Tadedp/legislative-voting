package edu.um.voterterminal.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Custom exception thrown when the private key is permanently invalidated
 * (e.g., due to a new biometric enrollment).
 */
class BiometricKeyInvalidatedException(message: String, cause: Throwable? = null) : Exception(message, cause)

@Singleton
class KeyStoreManager @Inject constructor() {

    private companion object {
        const val KEYSTORE_PROVIDER = "AndroidKeyStore"
        const val KEY_ALIAS = "voter_terminal_auth_key"
    }

    private val keyStore = KeyStore.getInstance(KEYSTORE_PROVIDER).apply {
        load(null)
    }

    /**
     * Generates a secp256k1 key pair in the Android Keystore.
     * Enforces biometric authentication for use and invalidation on biometric enrollment changes.
     * Requests attestation using the provided nationalId as the challenge.
     *
     * @return The X.509 certificate chain as a list of Base64 encoded strings.
     */
    fun generateKeyPairWithAttestation(nationalId: String): List<String> {
        val keyPairGenerator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_EC,
            KEYSTORE_PROVIDER
        )

        val parameterSpec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_SIGN
        )
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setUserAuthenticationRequired(true)
            // Invalidate key if new fingerprints/faces are added to the device
            .setInvalidatedByBiometricEnrollment(true)
            .setAttestationChallenge(nationalId.toByteArray(Charsets.UTF_8))
            .build()

        keyPairGenerator.initialize(parameterSpec)
        keyPairGenerator.generateKeyPair()

        val certificateChain = keyStore.getCertificateChain(KEY_ALIAS)
            ?: throw IllegalStateException("Failed to retrieve certificate chain from Keystore")

        return certificateChain.map { cert ->
            android.util.Base64.encodeToString(cert.encoded, android.util.Base64.NO_WRAP)
        }
    }

    /**
     * Retrieves the initialized [Signature] object for signing payloads.
     *
     * @throws BiometricKeyInvalidatedException if the key has been invalidated by a biometric enrollment change.
     */
    fun getSignature(): Signature {
        try {
            val privateKey = keyStore.getKey(KEY_ALIAS, null) as? PrivateKey
                ?: throw IllegalStateException("Auth key not found in Keystore. Device not provisioned.")

            val signature = Signature.getInstance("SHA256withECDSA")
            signature.initSign(privateKey)
            return signature
        } catch (e: KeyPermanentlyInvalidatedException) {
            throw BiometricKeyInvalidatedException("The biometric key was permanently invalidated.", e)
        }
    }

    /**
     * Deletes the cryptographic key pair from the Keystore.
     * Used by the Device Wipe Protocol.
     */
    fun clearKey() {
        if (keyStore.containsAlias(KEY_ALIAS)) {
            keyStore.deleteEntry(KEY_ALIAS)
        }
    }
}
