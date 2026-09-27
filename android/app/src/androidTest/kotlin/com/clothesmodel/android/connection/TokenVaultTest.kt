package com.clothesmodel.android.connection

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.security.KeyStore
import javax.crypto.SecretKey
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TokenVaultTest {
    @Test fun persistsCiphertextAndKeepsTheKeyNonExportable() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val vault = TokenVault(context)
        val token = "instrumentation-only-app-token"
        vault.save(token)

        val preferences = context.getSharedPreferences("secure_connection", 0)
        assertFalse(preferences.all.values.any { it == token })
        assertTrue(preferences.getString("ciphertext", null)?.isNotBlank() == true)

        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val key = store.getKey("clothes-model-app-token", null) as SecretKey
        assertNull(key.encoded)
        vault.clear()
    }

    @Test fun restoresConnectionAndRetainsUrlWhenAuthenticationExpires() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val firstVault = TokenVault(context)
        val firstStore = ConnectionStore(context, firstVault)
        firstStore.connected("https://example.test/", "process-recreation-token")

        val restoredVault = TokenVault(context)
        val restoredStore = ConnectionStore(context, restoredVault)
        val restored = restoredStore.snapshot()
        assertEquals("https://example.test/", restored.serverUrl)
        assertTrue(restored.authenticated)
        assertEquals("process-recreation-token", restoredVault.read())

        restoredStore.authenticationExpired()
        val expired = restoredStore.snapshot()
        assertEquals("https://example.test/", expired.serverUrl)
        assertFalse(expired.authenticated)
        assertNull(restoredVault.read())
    }
}
