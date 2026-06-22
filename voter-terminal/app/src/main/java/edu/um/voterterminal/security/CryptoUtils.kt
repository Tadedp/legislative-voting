package edu.um.voterterminal.security

import java.security.SecureRandom

object CryptoUtils {
    /**
     * Generates a 32-byte secure random salt and returns it as a mutable CharArray
     * containing its hexadecimal representation.
     * Returning a CharArray instead of a String allows for explicit memory wiping
     * before garbage collection, preventing extraction from JVM heap dumps.
     */
    fun generateVolatileSalt(): CharArray {
        val secureRandom = SecureRandom()
        val saltBytes = ByteArray(32)
        secureRandom.nextBytes(saltBytes)
        
        val hexChars = CharArray(64)
        val hexArray = "0123456789abcdef".toCharArray()
        for (j in saltBytes.indices) {
            val v = saltBytes[j].toInt() and 0xFF
            hexChars[j * 2] = hexArray[v ushr 4]
            hexChars[j * 2 + 1] = hexArray[v and 0x0F]
        }
        
        // Wipe intermediate byte array
        saltBytes.fill(0)
        
        return hexChars
    }
}
