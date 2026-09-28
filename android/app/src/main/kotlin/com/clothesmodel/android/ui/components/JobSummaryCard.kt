package com.clothesmodel.android.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.clothesmodel.android.assets.AssetImage
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing
import com.clothesmodel.android.ui.theme.LocalAtelierTokens
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val timeFormatter = DateTimeFormatter.ofPattern("MM-dd HH:mm")

fun formatJobTime(value: OffsetDateTime): String =
    value.atZoneSameInstant(ZoneId.systemDefault()).format(timeFormatter)

@Composable
fun JobSummaryCard(
    job: JobModel,
    imageLoader: AuthenticatedImageLoader,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val output = job.candidates.asSequence().flatMap { it.outputs.asSequence() }.firstOrNull()
    Surface(
        onClick = onClick,
        shape = AtelierShapes.Secondary,
        color = MaterialTheme.colorScheme.surface,
        modifier = modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (output != null && output.contentAvailable) {
                AssetImage(
                    assetId = output.assetId,
                    loader = imageLoader,
                    contentDescription = "任务结果缩略图",
                    modifier = Modifier.size(64.dp),
                )
            } else {
                DeletedContentPlaceholder(
                    label = "素材已删除",
                    modifier = Modifier.size(64.dp),
                )
            }
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs),
            ) {
                Text(
                    text = job.providerLabel,
                    style = MaterialTheme.typography.titleMedium,
                )
                StatusMarker(
                    status = job.state.toAtelierStatus(),
                    label = job.state.statusLabel(),
                )
                Text(
                    text = "${job.candidates.size} 个候选 · ${formatJobTime(job.updatedAt)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                job.blockReason?.let { reason ->
                    Text(
                        text = reason.blockLabel(),
                        style = MaterialTheme.typography.labelMedium,
                        color = LocalAtelierTokens.current.warningInk,
                    )
                }
            }
        }
    }
}
