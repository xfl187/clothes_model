package com.clothesmodel.android.connection

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.BuildConfig
import com.clothesmodel.android.imports.PendingImportRecovery
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ConnectionUiState(
    val serverUrl: String = "",
    val token: String = "",
    val loading: Boolean = true,
    val connected: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ConnectionViewModel @Inject constructor(
    @param:ApplicationContext private val context: Context,
) : ViewModel() {
    private val vault = TokenVault(context)
    private val store = ConnectionStore(context, vault)
    private val verifier = ConnectionVerifier()
    private val mutableState = MutableStateFlow(ConnectionUiState())
    val state: StateFlow<ConnectionUiState> = mutableState.asStateFlow()

    init {
        viewModelScope.launch {
            val saved = store.snapshot()
            mutableState.value = mutableState.value.copy(
                serverUrl = saved.serverUrl.orEmpty(),
                connected = saved.authenticated,
                loading = false,
            )
            if (saved.authenticated) verifySavedConnection()
        }
    }

    fun updateServerUrl(value: String) {
        mutableState.value = mutableState.value.copy(serverUrl = value, error = null)
    }

    fun updateToken(value: String) {
        mutableState.value = mutableState.value.copy(token = value, error = null)
    }

    fun connect() {
        val current = mutableState.value
        viewModelScope.launch {
            mutableState.value = current.copy(loading = true, connected = false, error = null)
            val url = runCatching {
                ServerEndpoint.normalize(
                    current.serverUrl,
                    BuildConfig.LOCAL_HTTP_HOSTS.split(',').filter(String::isNotBlank).toSet(),
                )
            }.getOrElse {
                mutableState.value = current.copy(loading = false, error = it.message)
                return@launch
            }
            store.rememberUrl(url)
            applyResult(url, current.token, verifier.verify(url, current.token))
        }
    }

    private suspend fun verifySavedConnection() {
        val token = vault.read() ?: return store.authenticationExpired()
        val url = store.snapshot().serverUrl ?: return store.authenticationExpired()
        mutableState.value = mutableState.value.copy(loading = true)
        applyResult(url, token, verifier.verify(url, token))
    }

    private suspend fun applyResult(url: String, token: String, result: ConnectionResult) {
        when (result) {
            ConnectionResult.Connected -> {
                store.connected(url, token)
                PendingImportRecovery.resume(context)
                mutableState.value = ConnectionUiState(
                    serverUrl = url,
                    connected = true,
                    loading = false,
                )
            }
            ConnectionResult.InvalidToken -> {
                store.authenticationExpired()
                mutableState.value = mutableState.value.copy(
                    serverUrl = url,
                    token = "",
                    loading = false,
                    connected = false,
                    error = "App Token 无效或已失效，请重新输入。",
                )
            }
            ConnectionResult.WrongScope -> {
                store.authenticationExpired()
                mutableState.value = mutableState.value.copy(
                    serverUrl = url,
                    token = "",
                    loading = false,
                    connected = false,
                    error = "该凭据不是 App Token。",
                )
            }
            ConnectionResult.Unavailable -> mutableState.value = mutableState.value.copy(
                serverUrl = url,
                token = "",
                loading = false,
                connected = false,
                error = "无法连接服务器，请检查地址和网络。",
            )
        }
    }
}
