package com.atlas.data.local

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Phase 12 / SECURITY_PLAN.md S4: shared helper so ApiKeyStore and
 * ServerConfigStore (both single-file SharedPreferences stores) get the
 * same encryption-at-rest without duplicating the MasterKey/
 * EncryptedSharedPreferences setup twice.
 *
 * Falls back to plain SharedPreferences only if creating the encrypted
 * store genuinely fails (e.g. a device-specific Keystore problem) -
 * logged loudly rather than silently, since a silent fallback here would
 * quietly undo the whole point of this class. This is a defensive
 * last-resort, not an expected path.
 */
internal object EncryptedPrefs {
    private const val TAG = "EncryptedPrefs"

    fun create(context: Context, fileName: String): SharedPreferences {
        return try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                context,
                fileName,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create EncryptedSharedPreferences for '$fileName' - falling back to plain SharedPreferences", e)
            context.getSharedPreferences(fileName, Context.MODE_PRIVATE)
        }
    }
}
