package edu.um.voterterminal

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Application subclass required by Hilt for dependency injection code generation.
 * Registered in AndroidManifest.xml via `android:name=".VoterTerminalApp"`.
 */
@HiltAndroidApp
class VoterTerminalApp : Application()
