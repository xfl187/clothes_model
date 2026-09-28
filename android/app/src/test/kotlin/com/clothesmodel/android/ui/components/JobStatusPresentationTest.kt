package com.clothesmodel.android.ui.components

import com.clothesmodel.android.ui.theme.AtelierStatus
import org.junit.Assert.assertEquals
import org.junit.Test

class JobStatusPresentationTest {
    @Test
    fun partialSuccessIsDistinctFromSuccess() {
        assertEquals(
            AtelierStatus.PARTIAL_SUCCESS,
            com.clothesmodel.android.data.JobStateDomain.PARTIALLY_SUCCEEDED.toAtelierStatus(),
        )
        assertEquals(
            AtelierStatus.SUCCEEDED,
            com.clothesmodel.android.data.JobStateDomain.SUCCEEDED.toAtelierStatus(),
        )
    }

    @Test
    fun waitingProviderAndNeedsAttentionRemainDistinct() {
        assertEquals(
            "等待 Provider，恢复后自动继续",
            com.clothesmodel.android.data.JobStateDomain.WAITING_PROVIDER.statusLabel(),
        )
        assertEquals(
            "结果状态不确定，需要处理",
            com.clothesmodel.android.data.JobStateDomain.NEEDS_ATTENTION.statusLabel(),
        )
    }

    @Test
    fun blockReasonsAreHumanReadable() {
        assertEquals(
            "Provider 暂时离线",
            com.clothesmodel.android.data.BlockReasonDomain.PROVIDER_OFFLINE.blockLabel(),
        )
        assertEquals(
            "等待释放存储空间",
            com.clothesmodel.android.data.BlockReasonDomain.STORAGE_CAPACITY.blockLabel(),
        )
    }
}
