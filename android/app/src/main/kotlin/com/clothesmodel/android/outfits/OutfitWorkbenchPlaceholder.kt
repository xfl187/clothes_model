package com.clothesmodel.android.outfits

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.theme.AtelierSpacing

/**
 * Temporary workbench entry. Task 11 replaces this with the layered workbench.
 */
@Composable
fun OutfitWorkbenchPlaceholder(
    sessionId: String,
    onBack: () -> Unit,
) {
    AtelierScaffold(title = "穿搭工作台", onBack = onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
            Text(
                text = "会话 ${sessionId.take(8)} 已就绪。",
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                text = "工作台将在下一步实现逐层叠加与候选确认。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
