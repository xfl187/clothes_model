package com.clothesmodel.android.connection

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.connectionDataStore by preferencesDataStore("connection_state")

data class ConnectionState(
    val serverUrl: String? = null,
    val authenticated: Boolean = false,
    val serverInstanceId: String? = null,
    val ownerScopeId: String? = null,
)

class ConnectionStore(private val context: Context, private val vault: TokenVault) {
    val state: Flow<ConnectionState> = context.connectionDataStore.data.map {
        ConnectionState(
            it[URL],
            it[AUTHENTICATED] == true && vault.read() != null,
            it[SERVER_INSTANCE_ID],
            it[OWNER_SCOPE_ID],
        )
    }

    suspend fun connected(
        url: String,
        token: String,
        serverInstanceId: String? = null,
        ownerScopeId: String? = null,
    ) {
        vault.save(token)
        context.connectionDataStore.edit {
            it[URL] = url
            it[AUTHENTICATED] = true
            if (serverInstanceId != null) it[SERVER_INSTANCE_ID] = serverInstanceId
            if (ownerScopeId != null) it[OWNER_SCOPE_ID] = ownerScopeId
        }
    }

    suspend fun authenticationExpired() {
        vault.clear()
        context.connectionDataStore.edit { it[AUTHENTICATED] = false }
    }

    suspend fun rememberUrl(url: String) {
        context.connectionDataStore.edit {
            it[URL] = url
            it[AUTHENTICATED] = false
        }
    }

    suspend fun snapshot(): ConnectionState = state.first()

    companion object {
        private val URL = stringPreferencesKey("server_url")
        private val AUTHENTICATED = booleanPreferencesKey("authenticated")
        private val SERVER_INSTANCE_ID = stringPreferencesKey("server_instance_id")
        private val OWNER_SCOPE_ID = stringPreferencesKey("owner_scope_id")
    }
}
