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
fun MissingTargetScreen(onBack: () -> Unit) {
    PlaceholderScreen(
        title = "未找到内容",
        message = "目标不存在或已被删除。",
        onBack = onBack,
    )
}
