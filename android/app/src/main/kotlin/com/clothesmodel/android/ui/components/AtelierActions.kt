package com.clothesmodel.android.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.TextFieldColors
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.dp
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing
import com.clothesmodel.android.ui.theme.LocalAtelierTokens
import androidx.compose.material3.Button as MaterialButton
import androidx.compose.material3.OutlinedButton as MaterialOutlinedButton

@Composable
fun AtelierButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shape: Shape = AtelierShapes.PrimaryButton,
    content: @Composable RowScope.() -> Unit,
) {
    MaterialButton(
        onClick = onClick,
        modifier = modifier.sizeIn(minHeight = AtelierSpacing.primaryButtonMinHeight),
        enabled = enabled,
        shape = shape,
        colors = ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.primary,
            contentColor = MaterialTheme.colorScheme.onPrimary,
            disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant,
            disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
        ),
        content = content,
    )
}

@Composable
fun AtelierOutlinedButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shape: Shape = AtelierShapes.Secondary,
    content: @Composable RowScope.() -> Unit,
) {
    val tokens = LocalAtelierTokens.current
    MaterialOutlinedButton(
        onClick = onClick,
        modifier = modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
        enabled = enabled,
        shape = shape,
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = MaterialTheme.colorScheme.primary,
            disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
        ),
        border = BorderStroke(
            1.dp,
            if (enabled) MaterialTheme.colorScheme.primary else tokens.line,
        ),
        content = content,
    )
}

@Composable
fun atelierOutlinedTextFieldColors(): TextFieldColors = OutlinedTextFieldDefaults.colors(
    focusedTextColor = MaterialTheme.colorScheme.onSurface,
    unfocusedTextColor = MaterialTheme.colorScheme.onSurface,
    disabledTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
    cursorColor = MaterialTheme.colorScheme.primary,
    focusedLabelColor = MaterialTheme.colorScheme.primary,
    unfocusedLabelColor = MaterialTheme.colorScheme.onSurfaceVariant,
    disabledLabelColor = MaterialTheme.colorScheme.onSurfaceVariant,
    focusedPlaceholderColor = MaterialTheme.colorScheme.onSurfaceVariant,
    unfocusedPlaceholderColor = MaterialTheme.colorScheme.onSurfaceVariant,
    focusedBorderColor = MaterialTheme.colorScheme.primary,
    unfocusedBorderColor = MaterialTheme.colorScheme.outline,
    disabledBorderColor = MaterialTheme.colorScheme.outline,
    errorTextColor = MaterialTheme.colorScheme.onSurface,
    errorLabelColor = MaterialTheme.colorScheme.error,
    errorBorderColor = MaterialTheme.colorScheme.error,
)
