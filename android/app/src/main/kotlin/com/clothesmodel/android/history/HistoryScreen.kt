package com.clothesmodel.android.history

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.JobSummaryCard
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
fun HistoryRoute(
    onOpenJob: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: HistoryViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    HistoryScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        onOpenJob = onOpenJob,
        onRefresh = viewModel::refresh,
        onLoadMore = viewModel::loadMore,
    )
}

@Composable
fun HistoryScreen(
    state: HistoryUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onOpenJob: (String) -> Unit,
    onRefresh: () -> Unit,
    onLoadMore: () -> Unit,
) {
    AtelierScaffold(title = "历史", scrollable = false) {
        when {
            state.loading && state.jobs.isEmpty() -> LoadingState(label = "正在读取任务历史")
            state.error != null && state.jobs.isEmpty() -> InlineProblem(
                message = state.error.detail,
                retryLabel = "重试",
                onRetry = onRefresh,
            )

            state.jobs.isEmpty() -> EmptyState(
                title = "还没有任务",
                message = "创建第一个精准换装后，全部状态都会显示在这里。",
            )

            else -> LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(0.dp),
                verticalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
            ) {
                if (state.stale) {
                    item {
                        Text("当前显示的是上一次同步结果，网络恢复后会自动刷新。")
                    }
                }
                items(state.jobs, key = { it.id.toString() }) { job ->
                    JobSummaryCard(
                        job = job,
                        imageLoader = imageLoader,
                        onClick = { onOpenJob(job.id.toString()) },
                    )
                }
                if (state.hasMore) {
                    item {
                        OutlinedButton(
                            onClick = onLoadMore,
                            enabled = !state.loadingMore,
                            modifier = Modifier
                                .fillMaxWidth()
                                .sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                        ) {
                            Text(if (state.loadingMore) "正在加载" else "加载更多")
                        }
                    }
                }
            }
        }
    }
}
