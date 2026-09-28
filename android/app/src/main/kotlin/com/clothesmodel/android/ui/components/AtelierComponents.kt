package com.clothesmodel.android.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing
import com.clothesmodel.android.ui.theme.AtelierStatus
import com.clothesmodel.android.ui.theme.LocalAtelierTokens

@Composable
fun SectionHeading(
    text: String,
    modifier: Modifier = Modifier,
    supporting: String? = null,
) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs)) {
        Text(
            text = text,
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.semantics { heading() },
        )
        if (supporting != null) {
            Text(
                text = supporting,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun StatusMarker(
    status: AtelierStatus,
    label: String,
    modifier: Modifier = Modifier,
) {
    val tokens = LocalAtelierTokens.current
    val markerColor = when (status) {
        AtelierStatus.SUCCEEDED, AtelierStatus.PARTIAL_SUCCESS -> tokens.success
        AtelierStatus.WAITING_PROVIDER -> tokens.warningInk
        AtelierStatus.FAILED -> tokens.error
        AtelierStatus.RUNNING -> tokens.plum
        AtelierStatus.NEEDS_ATTENTION -> tokens.plumDeep
        AtelierStatus.QUEUED, AtelierStatus.PREPARING,
        AtelierStatus.CANCELLED,
        -> tokens.muted
    }
    val markerShape = when (status) {
        AtelierStatus.NEEDS_ATTENTION, AtelierStatus.FAILED -> AtelierShapes.Secondary
        else -> CircleShape
    }
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm),
    ) {
        Box(
            modifier = Modifier
                .size(12.dp)
                .background(markerColor, markerShape)
                .semantics { role = Role.Image },
        )
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
fun EntityCard(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    status: AtelierStatus? = null,
    statusLabel: String? = null,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
) {
    val surfaceModifier = if (onClick != null) {
        modifier.fillMaxWidth().semantics { role = Role.Button }
    } else {
        modifier.fillMaxWidth()
    }
    Surface(
        onClick = onClick ?: {},
        enabled = onClick != null,
        modifier = surfaceModifier,
        shape = AtelierShapes.Secondary,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, LocalAtelierTokens.current.line),
    ) {
        Row(
            modifier = Modifier.padding(AtelierSpacing.lg).fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs),
            ) {
                Text(text = title, style = MaterialTheme.typography.titleMedium)
                if (subtitle != null) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (status != null && statusLabel != null) {
                    StatusMarker(status = status, label = statusLabel)
                }
            }
            trailing?.invoke()
        }
    }
}

@Composable
fun InlineProblem(
    message: String,
    modifier: Modifier = Modifier,
    retryLabel: String? = null,
    onRetry: (() -> Unit)? = null,
) {
    val tokens = LocalAtelierTokens.current
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = AtelierShapes.Secondary,
        color = tokens.warningSurface,
    ) {
        Column(
            modifier = Modifier.padding(AtelierSpacing.lg),
            verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm),
        ) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodyMedium,
                color = tokens.warningInk,
            )
            if (retryLabel != null && onRetry != null) {
                OutlinedButton(
                    onClick = onRetry,
                    modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                ) { Text(retryLabel) }
            }
        }
    }
}

@Composable
fun EmptyState(
    title: String,
    message: String,
    modifier: Modifier = Modifier,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(AtelierSpacing.xxl),
        verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(text = title, style = MaterialTheme.typography.titleMedium)
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (actionLabel != null && onAction != null) {
            Button(
                onClick = onAction,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text(actionLabel) }
        }
    }
}

@Composable
fun LoadingState(
    modifier: Modifier = Modifier,
    label: String = "正在加载",
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(AtelierSpacing.xxl),
        verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Text(text = label, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
fun DeletedContentPlaceholder(
    label: String,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = AtelierShapes.Thumbnail,
        color = LocalAtelierTokens.current.mist,
    ) {
        Box(
            modifier = Modifier.fillMaxSize().padding(AtelierSpacing.md),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun ConfirmationDialog(
    title: String,
    message: String,
    confirmLabel: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    destructive: Boolean = false,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(
                    text = confirmLabel,
                    color = if (destructive) {
                        LocalAtelierTokens.current.error
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        },
    )
}

@Composable
fun BackButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    IconButton(
        onClick = onClick,
        modifier = modifier.sizeIn(
            minWidth = AtelierSpacing.minTouchTarget,
            minHeight = AtelierSpacing.minTouchTarget,
        ),
    ) {
        Text(text = "返回", style = MaterialTheme.typography.labelLarge)
    }
}
