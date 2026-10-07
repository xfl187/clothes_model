package com.clothesmodel.android.connection

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.ui.components.AtelierButton
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.components.atelierOutlinedTextFieldColors
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
fun ConnectionRoute(
    onConnected: () -> Unit = {},
    viewModel: ConnectionViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.connected) {
        if (state.connected) onConnected()
    }
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
    val fieldColors = atelierOutlinedTextFieldColors()
    AtelierScaffold(title = "连接服务器") {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
            SectionHeading(
                text = if (connected) "服务器已连接" else "验证固定服务器",
                supporting = "地址会保留；令牌失效时只需重新认证，服务端任务不会取消。",
            )
            OutlinedTextField(
                value = serverUrl,
                onValueChange = onServerUrlChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("服务器地址") },
                placeholder = { Text("例如：http://127.0.0.1:18000") },
                singleLine = true,
                textStyle = MaterialTheme.typography.bodyLarge,
                colors = fieldColors,
            )
            OutlinedTextField(
                value = token,
                onValueChange = onTokenChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("App Token") },
                visualTransformation = PasswordVisualTransformation(),
                singleLine = true,
                textStyle = MaterialTheme.typography.bodyLarge,
                colors = fieldColors,
            )
            error?.let { InlineProblem(message = it) }
            AtelierButton(
                onClick = onConnect,
                enabled = !loading && serverUrl.isNotBlank() && token.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(AtelierSpacing.xl),
                        strokeWidth = AtelierSpacing.xs / 2,
                    )
                } else {
                    Text("验证并连接")
                }
            }
        }
    }
}
