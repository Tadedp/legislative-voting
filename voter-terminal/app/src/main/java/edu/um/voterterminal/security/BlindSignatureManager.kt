package edu.um.voterterminal.security

import org.bouncycastle.crypto.digests.SHA256Digest
import org.bouncycastle.crypto.engines.RSABlindingEngine
import org.bouncycastle.crypto.generators.RSABlindingFactorGenerator
import org.bouncycastle.crypto.params.RSABlindingParameters
import org.bouncycastle.crypto.signers.PSSSigner
import org.bouncycastle.util.io.pem.PemReader
import java.io.StringReader
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.interfaces.RSAPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import javax.inject.Inject
import javax.inject.Singleton
import org.bouncycastle.crypto.params.RSAKeyParameters

/**
 * Singleton to handle the volatile state and BouncyCastle math for Blind Signatures.
 */
@Singleton
class BlindSignatureManager @Inject constructor() {

    private var activeVotingRoundId: String? = null
    private var ephemeralPrivateKey: PrivateKey? = null
    private var ephemeralPublicKeyHex: String? = null
    private var bcBlindingFactor: java.math.BigInteger? = null
    private var cachedBlindedTokenHex: String? = null
    
    // Store the signed blinded payload from the server
    private var signedBlindedPayload: String? = null

    /**
     * Prepares the blinded token using the server's RSA public key.
     * Generates a new ephemeral ECDSA key internally.
     */
    fun prepareBlindedToken(votingRoundId: String, serverPublicKeyPem: String): Pair<String, String> {
        if (votingRoundId == activeVotingRoundId && ephemeralPublicKeyHex != null && cachedBlindedTokenHex != null) {
            return Pair(cachedBlindedTokenHex!!, ephemeralPublicKeyHex!!)
        }
        
        activeVotingRoundId = votingRoundId
        
        // 1. Generate Ephemeral ECDSA secp256r1 key
        val keyPairGenerator = KeyPairGenerator.getInstance("EC")
        keyPairGenerator.initialize(ECGenParameterSpec("secp256r1"))
        val keyPair = keyPairGenerator.generateKeyPair()
        ephemeralPrivateKey = keyPair.private
        
        val ephemeralPublicKeyBytes = keyPair.public.encoded
        this.ephemeralPublicKeyHex = ephemeralPublicKeyBytes.toHexString()
        
        // 2. We do NOT pre-digest the public key because PSSSigner internally digests it.
        val token = ephemeralPublicKeyBytes
        
        // 3. Load Server RSA Public Key from PEM
        val rsaPublicKey = loadRsaPublicKey(serverPublicKeyPem)
        val rsaKeyParams = RSAKeyParameters(false, rsaPublicKey.modulus, rsaPublicKey.publicExponent)
        
        // 4. Generate Blinding Factor
        val blindingFactorGenerator = RSABlindingFactorGenerator()
        blindingFactorGenerator.init(rsaKeyParams)
        val factor = blindingFactorGenerator.generateBlindingFactor()
        this.bcBlindingFactor = factor
        
        // 5. Blind the token
        val blindingParams = RSABlindingParameters(rsaKeyParams, factor)
        val blindingEngine = RSABlindingEngine()
        
        val pssSigner = PSSSigner(blindingEngine, SHA256Digest(), SHA256Digest(), 32, 1)
        pssSigner.init(true, blindingParams)
        pssSigner.update(token, 0, token.size)
        val blindedTokenBytes = pssSigner.generateSignature()
        
        val blindedTokenHex = blindedTokenBytes.toHexString()
        this.cachedBlindedTokenHex = blindedTokenHex
        
        return Pair(blindedTokenHex, this.ephemeralPublicKeyHex!!)
    }
    
    fun setAuthorizedPayload(votingRoundId: String, payload: String) {
        if (votingRoundId == activeVotingRoundId) {
            signedBlindedPayload = payload
        }
    }
    
    fun isAuthorized(votingRoundId: String): Boolean {
        return activeVotingRoundId == votingRoundId && signedBlindedPayload != null
    }

    /**
     * Unblinds the server signature and signs the vote anonymously (Phase 2).
     */
    fun generateAnonymousPayload(voteValue: String, serverPublicKeyPem: String): Triple<String, String, String> {
        val privKey = ephemeralPrivateKey ?: throw IllegalStateException("Ephemeral key missing")
        val pubKeyHex = ephemeralPublicKeyHex ?: throw IllegalStateException("Ephemeral public key missing")
        val signedHex = signedBlindedPayload ?: throw IllegalStateException("No signed blinded payload")
        val factor = bcBlindingFactor ?: throw IllegalStateException("No blinding factor")

        // 1. Unblind Server Signature
        val rsaPublicKey = loadRsaPublicKey(serverPublicKeyPem)
        val rsaKeyParams = RSAKeyParameters(false, rsaPublicKey.modulus, rsaPublicKey.publicExponent)
        val blindingParams = RSABlindingParameters(rsaKeyParams, factor)
        
        val engine = RSABlindingEngine()
        engine.init(false, blindingParams)
        
        val signedBytes = signedHex.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        val unblindedBytes = engine.processBlock(signedBytes, 0, signedBytes.size)
        val serverSignatureHex = unblindedBytes.toHexString()
        
        // 2. Sign Vote Value with Ephemeral Key
        val signature = java.security.Signature.getInstance("SHA256withECDSA")
        signature.initSign(privKey)
        signature.update(voteValue.toByteArray(Charsets.UTF_8))
        val voteSignatureBytes = signature.sign()
        
        return Triple(pubKeyHex, serverSignatureHex, voteSignatureBytes.toHexString())
    }

    /**
     * Wipes all volatile cryptographic material associated with the blind signature.
     */
    fun wipeVolatileMemory() {
        ephemeralPrivateKey = null
        ephemeralPublicKeyHex = null
        bcBlindingFactor = null
        cachedBlindedTokenHex = null
        signedBlindedPayload = null
        activeVotingRoundId = null
        System.gc()
    }

    private fun loadRsaPublicKey(pemStr: String): RSAPublicKey {
        val reader = PemReader(StringReader(pemStr))
        val pemObject = reader.readPemObject()
        val spec = X509EncodedKeySpec(pemObject.content)
        val factory = KeyFactory.getInstance("RSA")
        return factory.generatePublic(spec) as RSAPublicKey
    }

    private fun ByteArray.toHexString(): String {
        return joinToString("") { "%02x".format(it) }
    }
}
