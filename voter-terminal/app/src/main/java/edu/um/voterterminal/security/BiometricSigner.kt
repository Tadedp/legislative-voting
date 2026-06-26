package edu.um.voterterminal.security

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import kotlinx.coroutines.suspendCancellableCoroutine
import java.security.Signature
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

@Singleton
class BiometricSigner @Inject constructor(
    private val keyStoreManager: KeyStoreManager
) {

    /**
     * Authenticates the user via BiometricPrompt and signs the canonical payload bytes.
     *
     * @param activity The [FragmentActivity] used to host the [BiometricPrompt].
     * @param payloadBytes The canonical JSON payload converted to UTF-8 bytes.
     * @return The resulting cryptographic signature as a lowercase Hexadecimal string.
     * @throws BiometricKeyInvalidatedException if the biometric key is invalidated.
     * @throws Exception for biometric cancellation or errors.
     */
    suspend fun authenticateAndSign(
        activity: FragmentActivity,
        payloadBytes: ByteArray,
        voteValue: String,
        specificReference: String
    ): String = suspendCancellableCoroutine { continuation ->

        val signature: Signature
        try {
            signature = keyStoreManager.getSignature()
        } catch (e: Exception) {
            continuation.resumeWithException(e)
            return@suspendCancellableCoroutine
        }

        val cryptoObject = BiometricPrompt.CryptoObject(signature)

        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Confirm Vote")
            .setSubtitle("Confirmando voto: $voteValue para $specificReference")
            .setNegativeButtonText("Cancel")
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setConfirmationRequired(true)
            .build()

        val biometricPrompt = BiometricPrompt(
            activity,
            ContextCompat.getMainExecutor(activity),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    continuation.resumeWithException(Exception("Biometric Error [$errorCode]: $errString"))
                }

                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    try {
                        val activeSignature = result.cryptoObject?.signature
                            ?: throw IllegalStateException("Signature object not found in CryptoObject")

                        // Update signature with the canonical payload bytes
                        activeSignature.update(payloadBytes)

                        // Generate the signature
                        val signatureBytes = activeSignature.sign()

                        // Convert to lowercase Hex string for Orchestrator bytes.fromhex() compatibility
                        val hexSignature = signatureBytes.toHexString()
                        continuation.resume(hexSignature)

                    } catch (e: Exception) {
                        continuation.resumeWithException(e)
                    }
                }

                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                    // Prompt remains open on failure, no need to resume continuation yet,
                    // unless you want to limit attempts. BiometricPrompt handles retries natively.
                }
            }
        )

        biometricPrompt.authenticate(promptInfo, cryptoObject)

        continuation.invokeOnCancellation {
            biometricPrompt.cancelAuthentication()
        }
    }

    /**
     * Extension to convert a ByteArray to a lowercase Hexadecimal string.
     */
    private fun ByteArray.toHexString(): String {
        return joinToString("") { "%02x".format(it) }
    }
}
