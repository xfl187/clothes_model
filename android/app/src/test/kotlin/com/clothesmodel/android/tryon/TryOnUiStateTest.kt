package com.clothesmodel.android.tryon

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TryOnUiStateTest {
    @Test
    fun generationRequiresBothPersistentAssetIds() {
        val person = UploadSelection("person-import", "completed", "person-asset")
        val garment = UploadSelection("garment-import", "completed", "garment-asset")
        assertFalse(TryOnUiState(person = person).canGenerate)
        assertTrue(TryOnUiState(person = person, garment = garment).canGenerate)
        assertFalse(TryOnUiState(person = person, garment = garment, busy = true).canGenerate)
    }

    @Test
    fun mapsServerAuthoritativeStatesToRecoveryAwareMessages() {
        assertEquals("正在生成，离开页面也会继续", jobStateMessage("running"))
        assertEquals("结果状态不确定，需要人工处理", jobStateMessage("needs_attention"))
        assertEquals("生成完成", jobStateMessage("succeeded"))
    }
}
