package com.clothesmodel.android.connection

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun ConnectionRoute(viewModel: ConnectionViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    ConnectionScreen(
        serverUrl = state.serverUrl,
        token = state.token,
        loading = state.loading,
        connected = state.connected,
        error = state.error,
        onServerUrlChange = viewModel::updateServerUrl,
        onTokenChange = viewModel::updateToken,
        onConnect = viewModel::connect,
    )
}

@Composable
fun ConnectionScreen(
    serverUrl: String,
    token: String,
    loading: Boolean,
    connected: Boolean,
    error: String?,
    onServerUrlChange: (String) -> Unit,
    onTokenChange: (String) -> Unit,
    onConnect: () -> Unit,
) {
    Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("连接固定服务器")
        Text("地址会保留；令牌失效时只需重新认证，服务端任务不会取消。")
        if (connected) Text("已验证连接")
        OutlinedTextField(serverUrl, onServerUrlChange, Modifier.fillMaxWidth(), label = { Text("服务器地址") }, singleLine = true)
        OutlinedTextField(token, onTokenChange, Modifier.fillMaxWidth(), label = { Text("App Token") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
        error?.let { Text(it) }
        Button(onClick = onConnect, enabled = !loading && serverUrl.isNotBlank() && token.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
            if (loading) CircularProgressIndicator() else Text("验证并连接")
        }
    }
}
