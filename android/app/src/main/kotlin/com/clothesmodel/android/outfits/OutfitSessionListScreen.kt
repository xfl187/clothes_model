package com.clothesmodel.android.outfits

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.ui.components.AtelierButton
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
fun OutfitSessionListRoute(
    onBack: () -> Unit,
    onOpenSession: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: OutfitSessionListViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    LaunchedEffect(state.createdSession) {
        val created = state.createdSession
        if (created != null) {
            onOpenSession(created.id.toString())
            viewModel.consumeCreated()
        }
    }
    OutfitSessionListScreen(
        state = state,
        onBack = onBack,
        onOpenSession = onOpenSession,
        onNew = viewModel::openPicker,
        onSelectPerson = viewModel::create,
        onDismissPicker = viewModel::closePicker,
        onToggleFavorite = viewModel::toggleFavorite,
        onRefresh = viewModel::refresh,
    )
}

@Composable
fun OutfitSessionListScreen(
    state: OutfitListUiState,
    onBack: () -> Unit,
    onOpenSession: (String) -> Unit,
    onNew: () -> Unit,
    onSelectPerson: (java.util.UUID) -> Unit,
    onDismissPicker: () -> Unit,
    onToggleFavorite: (com.clothesmodel.contract.model.OutfitSession) -> Unit,
    onRefresh: () -> Unit,
) {
    AtelierScaffold(title = "分层穿搭", onBack = onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
            Text(
                text = "在同一身体基底上逐件叠加衣物，每一步都可确认并保留可回退的版本。",
                style = MaterialTheme.typography.bodyLarge,
            )
            AtelierButton(
                onClick = onNew,
                shape = AtelierShapes.PrimaryButton,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("新建穿搭会话")
            }

            if (state.error != null) {
                InlineProblem(
                    message = state.error.detail,
                    retryLabel = "重试",
                    onRetry = onRefresh,
                )
            }

            if (state.pickerOpen) {
                SectionHeading(text = "选择人物素材")
                if (state.persons.isEmpty()) {
                    EmptyState(
                        title = "没有可用人物素材",
                        message = "先在素材库导入一张人物照片。",
                    )
                } else {
                    state.persons.forEach { person ->
                        Surface(
                            shape = AtelierShapes.Secondary,
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable(enabled = !state.creating) {
                                    onSelectPerson(person.id)
                                },
                        ) {
                            Text(
                                text = "人物素材 ${person.id.toString().take(8)}",
                                style = MaterialTheme.typography.titleMedium,
                                modifier = Modifier.padding(AtelierSpacing.lg),
                            )
                        }
                    }
                }
                TextButton(onClick = onDismissPicker) { Text("取消") }
            } else {
                SectionHeading(text = "我的穿搭会话")
                when {
                    state.loading && state.sessions.isEmpty() ->
                        LoadingState(label = "正在读取穿搭会话")

                    state.sessions.isEmpty() -> EmptyState(
                        title = "还没有穿搭会话",
                        message = "选择一张人物照片创建第一个分层穿搭会话。",
                    )

                    else -> state.sessions.forEach { session ->
                        Surface(
                            shape = AtelierShapes.Secondary,
                            color = MaterialTheme.colorScheme.surface,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onOpenSession(session.id.toString()) },
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(AtelierSpacing.lg),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs)) {
                                    Text(
                                        text = session.name,
                                        style = MaterialTheme.typography.titleMedium,
                                    )
                                    Text(
                                        text = "${session.branches.size} 个分支 · " +
                                            "${session.layerTypes.size} 种层级",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                TextButton(onClick = { onToggleFavorite(session) }) {
                                    Text(if (session.favorite) "已收藏" else "收藏")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
