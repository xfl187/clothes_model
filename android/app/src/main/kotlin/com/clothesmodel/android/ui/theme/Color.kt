package com.clothesmodel.android.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

object AtelierColors {
    val CanvasLight = Color(0xFFF3EFE9)
    val PaperLight = Color(0xFFFBF8F3)
    val MistLight = Color(0xFFECE7E1)
    val InkLight = Color(0xFF241F23)
    val MutedLight = Color(0xFF5F565D)
    val PlumLight = Color(0xFF69465F)
    val PlumDeepLight = Color(0xFF4A3043)
    val BlushLight = Color(0xFFDCC5CF)
    val LineLight = Color(0xFF948890)
    val SuccessLight = Color(0xFF426C56)
    val WarningLight = Color(0xFFF3DFB7)
    val WarningInkLight = Color(0xFF6B4B18)
    val ErrorLight = Color(0xFFA7433F)
    val ScrimLight = Color(0xFF241F23)

    val CanvasDark = Color(0xFF171417)
    val PaperDark = Color(0xFF211D20)
    val MistDark = Color(0xFF2B262A)
    val InkDark = Color(0xFFF3ECEF)
    val MutedDark = Color(0xFFD1C6CC)
    val PlumDark = Color(0xFFD5AFC3)
    val PlumDeepDark = Color(0xFF563A4E)
    val BlushDark = Color(0xFF563A4E)
    val LineDark = Color(0xFF71656C)
    val SuccessDark = Color(0xFF8FC3A2)
    val WarningDark = Color(0xFF4B391E)
    val WarningInkDark = Color(0xFFF1D18E)
    val ErrorDark = Color(0xFFF1A19B)
    val ScrimDark = Color(0xFF171417)
}

enum class AtelierStatus {
    QUEUED,
    WAITING_PROVIDER,
    PREPARING,
    RUNNING,
    NEEDS_ATTENTION,
    SUCCEEDED,
    PARTIAL_SUCCESS,
    FAILED,
    CANCELLED,
}

@Immutable
data class AtelierTokens(
    val canvas: Color,
    val paper: Color,
    val mist: Color,
    val ink: Color,
    val muted: Color,
    val plum: Color,
    val plumDeep: Color,
    val blush: Color,
    val line: Color,
    val success: Color,
    val warningSurface: Color,
    val warningInk: Color,
    val error: Color,
    val scrim: Color,
)

val LightAtelierTokens = AtelierTokens(
    canvas = AtelierColors.CanvasLight,
    paper = AtelierColors.PaperLight,
    mist = AtelierColors.MistLight,
    ink = AtelierColors.InkLight,
    muted = AtelierColors.MutedLight,
    plum = AtelierColors.PlumLight,
    plumDeep = AtelierColors.PlumDeepLight,
    blush = AtelierColors.BlushLight,
    line = AtelierColors.LineLight,
    success = AtelierColors.SuccessLight,
    warningSurface = AtelierColors.WarningLight,
    warningInk = AtelierColors.WarningInkLight,
    error = AtelierColors.ErrorLight,
    scrim = AtelierColors.ScrimLight,
)

val DarkAtelierTokens = AtelierTokens(
    canvas = AtelierColors.CanvasDark,
    paper = AtelierColors.PaperDark,
    mist = AtelierColors.MistDark,
    ink = AtelierColors.InkDark,
    muted = AtelierColors.MutedDark,
    plum = AtelierColors.PlumDark,
    plumDeep = AtelierColors.PlumDeepDark,
    blush = AtelierColors.BlushDark,
    line = AtelierColors.LineDark,
    success = AtelierColors.SuccessDark,
    warningSurface = AtelierColors.WarningDark,
    warningInk = AtelierColors.WarningInkDark,
    error = AtelierColors.ErrorDark,
    scrim = AtelierColors.ScrimDark,
)

val LocalAtelierTokens = staticCompositionLocalOf { LightAtelierTokens }

internal val LightColorScheme = lightColorScheme(
    primary = AtelierColors.PlumLight,
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = AtelierColors.BlushLight,
    onPrimaryContainer = AtelierColors.PlumDeepLight,
    secondary = AtelierColors.PlumLight,
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = AtelierColors.BlushLight,
    onSecondaryContainer = AtelierColors.PlumDeepLight,
    background = AtelierColors.CanvasLight,
    onBackground = AtelierColors.InkLight,
    surface = AtelierColors.PaperLight,
    onSurface = AtelierColors.InkLight,
    surfaceVariant = AtelierColors.MistLight,
    onSurfaceVariant = AtelierColors.MutedLight,
    outline = AtelierColors.LineLight,
    outlineVariant = AtelierColors.MistLight,
    error = AtelierColors.ErrorLight,
    onError = Color(0xFFFFFFFF),
)

internal val DarkColorScheme = darkColorScheme(
    primary = AtelierColors.PlumDark,
    onPrimary = AtelierColors.PlumDeepDark,
    primaryContainer = AtelierColors.BlushDark,
    onPrimaryContainer = AtelierColors.InkDark,
    secondary = AtelierColors.PlumDark,
    onSecondary = AtelierColors.PlumDeepDark,
    secondaryContainer = AtelierColors.BlushDark,
    onSecondaryContainer = AtelierColors.InkDark,
    background = AtelierColors.CanvasDark,
    onBackground = AtelierColors.InkDark,
    surface = AtelierColors.PaperDark,
    onSurface = AtelierColors.InkDark,
    surfaceVariant = AtelierColors.MistDark,
    onSurfaceVariant = AtelierColors.MutedDark,
    outline = AtelierColors.LineDark,
    outlineVariant = AtelierColors.MistDark,
    error = AtelierColors.ErrorDark,
    onError = AtelierColors.CanvasDark,
)
