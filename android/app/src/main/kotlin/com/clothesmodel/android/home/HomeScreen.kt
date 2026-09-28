package com.clothesmodel.android.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.JobSummaryCard
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
fun HomeRoute(
    onCreate: () -> Unit,
    onOpenJob: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    HomeScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        onCreate = onCreate,
        onOpenJob = onOpenJob,
        onRefresh = viewModel::refresh,
    )
}

@Composable
fun HomeScreen(
    state: HomeUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onCreate: () -> Unit,
    onOpenJob: (String) -> Unit,
    onRefresh: () -> Unit,
) {
    AtelierScaffold(title = "首页") {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xxl)) {
            Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                Text(
                    text = "私人试衣工作室",
                    style = MaterialTheme.typography.displayMedium,
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    text = "选择一张人物照片与一件衣物，生成尽量保持身份与背景的试穿结果。",
                    style = MaterialTheme.typography.bodyLarge,
                )
                Button(
                    onClick = onCreate,
                    shape = AtelierShapes.PrimaryButton,
                    modifier = Modifier
                        .fillMaxWidth()
                        .sizeIn(minHeight = AtelierSpacing.primaryButtonMinHeight),
                ) {
                    Text("开始精准换装")
                }
            }

            SectionHeading(
                text = "最近任务",
                supporting = "离开页面不会取消服务端任务。",
            )
            when {
                state.loading && state.recentJobs.isEmpty() -> LoadingState(label = "正在读取最近任务")
                state.error != null && state.recentJobs.isEmpty() -> InlineProblem(
                    message = state.error.detail,
                    retryLabel = "重试",
                    onRetry = onRefresh,
                )

                state.recentJobs.isEmpty() -> EmptyState(
                    title = "还没有任务",
                    message = "完成第一次精准换装后，最近的候选会显示在这里。",
                    actionLabel = "开始精准换装",
                    onAction = onCreate,
                )

                else -> {
                    if (state.stale) {
                        Text(
                            text = "当前显示的是上一次同步结果，网络恢复后会自动刷新。",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    state.recentJobs.forEach { job ->
                        JobSummaryCard(
                            job = job,
                            imageLoader = imageLoader,
                            onClick = { onOpenJob(job.id.toString()) },
                        )
                    }
                }
            }

            SectionHeading(text = "即将开放")
            ComingSoonCard(
                title = "分层穿搭",
                description = "在同一身体基底上叠加多件衣物，并保留可回退的版本。",
            )
            ComingSoonCard(
                title = "创意写真",
                description = "为同一人物生成不同风格的写真结果。",
            )
        }
    }
}

@Composable
private fun ComingSoonCard(title: String, description: String) {
    Surface(
        shape = AtelierShapes.Secondary,
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier
                .padding(AtelierSpacing.lg)
                .sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs),
        ) {
            Text(text = title, style = MaterialTheme.typography.titleMedium)
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "即将开放",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
