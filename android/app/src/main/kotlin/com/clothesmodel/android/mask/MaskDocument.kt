package com.clothesmodel.android.mask

import kotlin.math.min

enum class MaskTool { DRAW, ERASE }

data class MaskPoint(val x: Float, val y: Float)

data class MaskStroke(
    val tool: MaskTool,
    val radius: Float,
    val points: List<MaskPoint>,
)

data class MaskDocument(
    val strokes: List<MaskStroke> = emptyList(),
) {
    val isBlank: Boolean get() = strokes.none { it.tool == MaskTool.DRAW }

    fun startStroke(tool: MaskTool, radius: Float, point: MaskPoint): MaskDocument =
        copy(strokes = strokes + MaskStroke(tool, radius, listOf(point)))

    fun extendStroke(point: MaskPoint): MaskDocument =
        if (strokes.isEmpty()) this else copy(strokes = strokes.dropLast(1) + strokes.last().copy(points = strokes.last().points + point))

    fun undo(): MaskDocument = if (strokes.isEmpty()) this else copy(strokes = strokes.dropLast(1))

    fun clear(): MaskDocument = MaskDocument()
}

fun toPixel(point: MaskPoint, width: Int, height: Int): Pair<Float, Float> =
    point.x * width to point.y * height

fun brushRadiusPx(normalizedRadius: Float, width: Int, height: Int): Float =
    normalizedRadius * min(width, height)

val brushSizeOptions: List<Float> = listOf(0.04f, 0.08f, 0.14f)

fun MaskDocument.encode(): String =
    strokes.joinToString("\n") { stroke ->
        val points = stroke.points.joinToString(";") { "${it.x},${it.y}" }
        "${stroke.tool.name},${stroke.radius},$points"
    }

fun decodeMaskDocument(text: String): MaskDocument {
    if (text.isBlank()) return MaskDocument()
    val strokes = text.lineSequence().mapNotNull { line ->
        val parts = line.split(",", limit = 3)
        if (parts.size < 3) return@mapNotNull null
        val tool = runCatching { MaskTool.valueOf(parts[0]) }.getOrNull() ?: return@mapNotNull null
        val radius = parts[1].toFloatOrNull() ?: return@mapNotNull null
        val points = parts[2].split(";").mapNotNull { pair ->
            val coordinates = pair.split(",")
            if (coordinates.size != 2) return@mapNotNull null
            val x = coordinates[0].toFloatOrNull() ?: return@mapNotNull null
            val y = coordinates[1].toFloatOrNull() ?: return@mapNotNull null
            MaskPoint(x, y)
        }
        if (points.isEmpty()) null else MaskStroke(tool, radius, points)
    }.toList()
    return MaskDocument(strokes)
}
