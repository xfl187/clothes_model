package com.clothesmodel.android.mask

import kotlin.math.min
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MaskDocumentTest {
    @Test
    fun drawStrokesAndUndo() {
        var document = MaskDocument()
        assertTrue(document.isBlank)

        document = document.startStroke(MaskTool.DRAW, 0.1f, MaskPoint(0.1f, 0.1f))
        document = document.extendStroke(MaskPoint(0.5f, 0.5f))
        assertFalse(document.isBlank)
        assertEquals(2, document.strokes.first().points.size)

        document = document.undo()
        assertTrue(document.strokes.isEmpty())
    }

    @Test
    fun eraseAloneIsBlankAndClearResets() {
        var document = MaskDocument().startStroke(MaskTool.ERASE, 0.1f, MaskPoint(0.2f, 0.2f))
        assertTrue(document.isBlank)

        document = document.startStroke(MaskTool.DRAW, 0.1f, MaskPoint(0.3f, 0.3f))
        assertFalse(document.isBlank)
        document = document.clear()
        assertTrue(document.strokes.isEmpty())
        assertTrue(document.isBlank)
    }

    @Test
    fun normalizedPointsMapToPixels() {
        val (x, y) = toPixel(MaskPoint(0.25f, 0.5f), 800, 400)
        assertEquals(200f, x, 0.001f)
        assertEquals(200f, y, 0.001f)
    }

    @Test
    fun brushRadiusScalesWithShorterEdge() {
        assertEquals(min(100, 200) * 0.5f, brushRadiusPx(0.5f, 100, 200), 0.001f)
    }

    @Test
    fun brushOptionsAreAscending() {
        assertEquals(brushSizeOptions.sorted(), brushSizeOptions)
    }

    @Test
    fun documentRoundTripsThroughTextEncoding() {
        val document = MaskDocument()
            .startStroke(MaskTool.DRAW, 0.08f, MaskPoint(0.1f, 0.2f))
            .extendStroke(MaskPoint(0.9f, 0.8f))
            .startStroke(MaskTool.ERASE, 0.14f, MaskPoint(0.5f, 0.5f))
        val decoded = decodeMaskDocument(document.encode())
        assertEquals(document, decoded)
        assertTrue(decodeMaskDocument("").isBlank)
    }
}
