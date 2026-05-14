# SYSTEM SPECIFICATION: ANDROID EDGE VOTING MODULE

## 1. System Context & Tech Stack

You are an expert backend engineer. Your task is to build the "Voter Terminal," a native Android application deployed on mobile phones for a high-security Legislative Electronic Voting System, structured under a distributed software architecture based on decoupled modules. This module acts as the physical and cryptographic boundary for legislative intent. It holds no local business logic regarding session states, operating strictly as a stateless client driven by the Orchestrator's (the central API module) authoritative broadcasts.

* **Language:** Kotlin
* **UI Framework:** Jetpack Compose
* **Networking:** Ktor Client (Asynchronous REST & WebSockets via Coroutines/Flow)
* **Security & Crypto:** `androidx.biometric`, Android Hardware Keystore (`secp256k1`), `java.security.Signature`, Android Key Attestation.
* **Local Storage:** `EncryptedSharedPreferences` (strictly for the `device_token` and the self-generated hardware UUID).
* **Device Management:** Standard full-screen application.

## 2. Core Architectural & Security Directives

### 2.1 Hardware Anchor & Cryptographic Lifecycle

To guarantee Non-Repudiation, the application relies on the Android Trusted Execution Environment (TEE) / Secure Element (SE).

* **Key Generation:** Elliptic Curve (`secp256k1`).
* **Hardware Binding:** The `KeyGenParameterSpec` strictly enforces:
  * `setUserAuthenticationRequired(true)`: Unlocking the private key requires local biological validation.
  * `setInvalidatedByBiometricEnrollment(true)`: Any alteration to the OS-level biometric templates permanently destroys the Private Key, neutralizing malicious local actors.
* **Android Key Attestation (Proof of Hardware):** During key generation, the app must call `setAttestationChallenge()`. This instructs the hardware to output an X.509 Certificate Chain proving the key resides in the TEE and is biometric-bound.
* **The `CryptoObject` Wrapper:** The application MUST NOT use a simple `true/false` boolean from the `BiometricPrompt`. It must pass an initialized `Signature` instance wrapped in a `CryptoObject` to the prompt. The OS hardware will only unlock the Keystore specifically for that `Signature` object upon a successful biological read.

### 2.2 Network Resilience & Power Management

* **Stateless UI:** The UI is a direct reflection of a Kotlin `StateFlow` updated by the Ktor WebSocket.
* **Resynchronization:** Upon returning from the background, or if the WS drops, the app makes a synchronous REST call (`GET /sessions/current`) to rebuild its UI state before re-establishing the WS.
* **Doze Mode Mitigation:** To prevent the Wi-Fi radio from sleeping during a long session:
  * A Foreground Service maintains the Ktor WebSocket connection.
  * `WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON` is dynamically applied ONLY when a motion state is `VOTING_OPEN`.
* **Tapjacking Protection:** To prevent malicious overlays from tricking the user, Jetpack Compose UI modifiers must implement logic analogous to `setFilterTouchesWhenObscured(true)`.

### 2.3 Replay Attack Prevention

To prevent network sniffers from capturing a signed "YES" payload and re-transmitting it later, all signed payloads MUST include a cryptographic nonce (specifically, a high-precision `timestamp`). The backend will reject signatures if the timestamp is too old or duplicates a known submission.

### 2.4 Software Architecture & Design Principles

* **Clean Architecture and MVVM:** The codebase MUST follow the Clean Architecture and MVVM principles, separating the UI (View) from the Business Logic (ViewModel) and Data Sources.
* **Dependency Injection:** Hilt MUST be used for dependency injection to manage the lifecycle of the Ktor Client, Repository, and ViewModels.
* **Strict Concurrency:** All network operations MUST be performed asynchronously using Kotlin Coroutines (`withContext(Dispatchers.IO)`). The UI thread MUST NOT be blocked.
* **Error Handling:** Generic error handlers should be implemented in the ViewModel to catch network exceptions and translate them into user-friendly messages displayed via the UI state.

---

## 3. Operational Flows (Android Edge Perspective)

### 3.1 Flow 1: Device Provisioning & Key Generation (One-Time)

1. **Admin Trigger:** An IT Administrator accesses a hidden provisioning screen (via long-press gesture + Admin PIN).
2. **UUID Generation:** Upon first launch, the app generates a `UUIDv4` (`hardware_id`), storing it permanently in `EncryptedSharedPreferences`.
3. **RENAPER Challenge:** The app captures the Legislator's National ID and a live facial capture (Base64), transmitting it to the Orchestrator.
4. **KeyGen:** Upon an HTTP `200 OK`, the app generates the `secp256k1` key pair in the Keystore with an attestation challenge.
5. **Registration:** The app transmits the `hardware_id` and the **X.509 Certificate Chain** (Base64 encoded list) to the Orchestrator.
6. **Persistence:** The app stores the returned `device_token` securely. The UI transitions to the "Awaiting Session" screen.

### 3.2 Flow 2: The Nominal Vote (Plaintext Signing)

1. **Intent:** The Legislator taps "AFFIRMATIVE". The UI locks temporarily.
2. **Payload Construction:** Create JSON: `{"motion_id": "uuid", "vote_value": "AFFIRMATIVE", "timestamp": 168...}`.
3. **Biometric Prompt:** Trigger the UI prompt with the `CryptoObject`.
4. **Hardware Signing:** Upon a successful biological read, sign the payload bytes.
5. **Transmission:** POST the plaintext payload and Hex signature.
6. **Feedback:** Upon HTTP `201 Created`, the UI updates to a permanent "Vote Registered" state for that motion.

### 3.3 Flow 3: The Non-Nominal Vote (Double-Envelope Crypto)

1. **Intent:** The Legislator taps "AFFIRMATIVE".
2. **Inner Envelope (Encryption):**
   * Generate `receipt_id` (UUID).
   * Construct JSON: `{"receipt_id": "uuid", "vote_value": "AFFIRMATIVE"}`.
   * Encrypt JSON using the Session's Ephemeral Public Key (provided by Orchestrator state). *Result: Ciphertext*.
3. **Outer Envelope (Signing):**
   * Construct outer payload: `{"motion_id": "uuid", "encrypted_payload": "Ciphertext", "timestamp": 168...}`.
   * Trigger `BiometricPrompt` with `CryptoObject`.
   * Sign the outer payload bytes.
4. **Transmission:** POST the Ciphertext, outer payload, and Hex signature.

### 3.4 Flow 4: The Device Wipe Protocol (Remote Revocation)

1. **WS Trigger:** The Ktor WebSocket receives an event with `event_type == "DEVICE_WIPE_COMMAND"`.
2. **The Purge:** Delete the `device_token` and `hardware_id`, delete the Keystore alias, and close the WebSocket.
3. **UI Reset:** The app navigates to a hard-locked "Device Revoked" screen. It cannot be used again until the Admin Provisioning flow is restarted.

---

## 4. UI & State Machine (Jetpack Compose)

The UI dynamically adapts to the parliamentary rules dictated by the Orchestrator.

### 4.1 The Context Panel

During an active motion, the upper portion of the screen displays:

* The Motion `title`.
* The Motion `summary` (Scrollable text area providing the context of the bill).

### 4.2 Dynamic Voting Controls

The lower portion of the screen renders the voting buttons based on the current `VotingType`:

* **Always Present:** `AFFIRMATIVE` (Green) and `NEGATIVE` (Red).
* **Conditional:** `ABSTENTION` (Yellow) is ONLY rendered if the broadcasted state includes `allows_abstentions == true`.
* **Lock-out:** Once a vote is successfully transmitted, all buttons are disabled and visually dimmed to prevent confusion or duplicate submissions.

### 4.3 Abort State Recovery

If the WS receives a `MOTION_ABORTED` event, the UI instantly clears the "Vote Registered" lock-out and resets the buttons, preparing the legislator for the re-vote initiated by the Presidency.
