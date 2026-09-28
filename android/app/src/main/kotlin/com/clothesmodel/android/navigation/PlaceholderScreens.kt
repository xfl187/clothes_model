package com.clothesmodel.android.navigation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
internal fun PlaceholderScreen(
    title: String,
    message: String,
    onBack: (() -> Unit)? = null,
    action: Pair<String, () -> Unit>? = null,
) {
    AtelierScaffold(title = title, onBack = onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
            EmptyState(
                title = title,
                message = message,
                actionLabel = action?.first,
                onAction = action?.second,
            )
        }
    }
}

@Composable
fun CreateWizardRoute(
    onBack: () -> Unit,
    onCreated: (String) -> Unit,
) {
    PlaceholderScreen(
        title = "精准换装",
        message = "三步创建向导将在此显示。",
        onBack = onBack,
    )
}

@Composable
fun JobDetailRoute(
    jobId: String,
    onBack: () -> Unit,
    onOpenResults: (String) -> Unit,
) {
    PlaceholderScreen(
        title = "任务详情",
        message = "任务 $jobId 的候选与恢复操作将在此显示。",
        onBack = onBack,
    )
}

@Composable
fun ResultRoute(
    jobId: String,
    onBack: () -> Unit,
    onCompare: (String) -> Unit,
    onMask: (String) -> Unit,
) {
    PlaceholderScreen(
        title = "生成结果",
        message = "任务 $jobId 的结果网格将在此显示。",
        onBack = onBack,
    )
}

@Composable
fun CompareRoute(
    jobId: String,
    candidateId: String,
    onBack: () -> Unit,
) {
    PlaceholderScreen(
        title = "原图对比",
        message = "候选 $candidateId 的原图与结果对比将在此显示。",
        onBack = onBack,
    )
}

@Composable
fun MaskEditorRoute(
    jobId: String,
    candidateId: String,
    onBack: () -> Unit,
) {
    PlaceholderScreen(
        title = "遮罩修正",
        message = "候选 $candidateId 的遮罩编辑将在此显示。",
        onBack = onBack,
    )
}

@Composable
fun MissingTargetScreen(onBack: () -> Unit) {
    PlaceholderScreen(
        title = "未找到内容",
        message = "目标不存在或已被删除。",
        onBack = onBack,
    )
}
