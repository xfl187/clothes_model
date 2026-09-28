package com.clothesmodel.android.mask

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import androidx.core.graphics.createBitmap
import java.io.ByteArrayOutputStream

object MaskRenderer {
    fun render(document: MaskDocument, width: Int, height: Int): ByteArray {
        val safeWidth = width.coerceAtLeast(1)
        val safeHeight = height.coerceAtLeast(1)
        val bitmap = createBitmap(safeWidth, safeHeight)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeCap = Paint.Cap.ROUND
            strokeJoin = Paint.Join.ROUND
        }
        for (stroke in document.strokes) {
            val strokeWidth = brushRadiusPx(stroke.radius, safeWidth, safeHeight) * 2f
            paint.strokeWidth = strokeWidth
            paint.color = android.graphics.Color.WHITE
            paint.xfermode = if (stroke.tool == MaskTool.ERASE) {
                PorterDuffXfermode(PorterDuff.Mode.CLEAR)
            } else {
                null
            }
            if (stroke.points.size == 1) {
                val (x, y) = toPixel(stroke.points.first(), safeWidth, safeHeight)
                canvas.drawCircle(x, y, strokeWidth / 2f, paint)
            } else {
                val path = Path()
                stroke.points.forEachIndexed { index, point ->
                    val (x, y) = toPixel(point, safeWidth, safeHeight)
                    if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                canvas.drawPath(path, paint)
            }
        }
        val output = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
        bitmap.recycle()
        return output.toByteArray()
    }
}
