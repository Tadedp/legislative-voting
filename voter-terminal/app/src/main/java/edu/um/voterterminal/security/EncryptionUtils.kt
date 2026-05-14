package edu.um.voterterminal.security

import android.util.Base64
import java.security.KeyFactory
import java.security.spec.X509EncodedKeySpec
import javax.crypto.Cipher
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class EncryptionUtils @Inject constructor() {

    private companion object {
        const val CIPHER_ALGORITHM = "RSA/ECB/OAEPWithSHA-256AndMGF1Padding"
        const val KEY_ALGORITHM = "RSA"
    }

    /**
     * Encrypts the JSON payload (Inner Envelope) using the Orchestrator's
     * Ephemeral Public Key.
     *
     * @param payloadJson The JSON string to encrypt.
     * @param ephemeralPublicKeyBase64 The Base64-encoded X.509 SubjectPublicKeyInfo from the Orchestrator.
     * @return The Base64-encoded ciphertext.
     */
    fun encryptNonNominalPayload(payloadJson: String, ephemeralPublicKeyBase64: String): String {
        // Decode the public key
        val keyBytes = Base64.decode(ephemeralPublicKeyBase64, Base64.DEFAULT)
        val keySpec = X509EncodedKeySpec(keyBytes)
        val keyFactory = KeyFactory.getInstance(KEY_ALGORITHM)
        val publicKey = keyFactory.generatePublic(keySpec)

        // Initialize the Cipher
        val cipher = Cipher.getInstance(CIPHER_ALGORITHM)
        cipher.init(Cipher.ENCRYPT_MODE, publicKey)

        // Encrypt the payload
        val ciphertextBytes = cipher.doFinal(payloadJson.toByteArray(Charsets.UTF_8))

        // Return Base64 (NO_WRAP to avoid newlines in JSON payloads)
        return Base64.encodeToString(ciphertextBytes, Base64.NO_WRAP)
    }
}
