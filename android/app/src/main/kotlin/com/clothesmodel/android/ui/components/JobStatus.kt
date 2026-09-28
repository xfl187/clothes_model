package com.clothesmodel.android.ui.components

import com.clothesmodel.android.data.BlockReasonDomain
import com.clothesmodel.android.data.JobStateDomain
import com.clothesmodel.android.ui.theme.AtelierStatus

fun JobStateDomain.toAtelierStatus(): AtelierStatus = when (this) {
    JobStateDomain.QUEUED -> AtelierStatus.QUEUED
    JobStateDomain.WAITING_PROVIDER -> AtelierStatus.WAITING_PROVIDER
    JobStateDomain.PREPARING -> AtelierStatus.PREPARING
    JobStateDomain.RUNNING -> AtelierStatus.RUNNING
    JobStateDomain.NEEDS_ATTENTION -> AtelierStatus.NEEDS_ATTENTION
    JobStateDomain.SUCCEEDED -> AtelierStatus.SUCCEEDED
    JobStateDomain.PARTIALLY_SUCCEEDED -> AtelierStatus.PARTIAL_SUCCESS
    JobStateDomain.FAILED -> AtelierStatus.FAILED
    JobStateDomain.CANCELLED -> AtelierStatus.CANCELLED
    JobStateDomain.UNKNOWN -> AtelierStatus.QUEUED
}

fun JobStateDomain.statusLabel(): String = when (this) {
    JobStateDomain.QUEUED -> "已排队，等待执行"
    JobStateDomain.WAITING_PROVIDER -> "等待 Provider，恢复后自动继续"
    JobStateDomain.PREPARING -> "正在准备私有图片"
    JobStateDomain.RUNNING -> "正在生成，可离开页面"
    JobStateDomain.NEEDS_ATTENTION -> "结果状态不确定，需要处理"
    JobStateDomain.SUCCEEDED -> "生成完成"
    JobStateDomain.PARTIALLY_SUCCEEDED -> "部分候选成功"
    JobStateDomain.FAILED -> "生成失败"
    JobStateDomain.CANCELLED -> "已取消"
    JobStateDomain.UNKNOWN -> "状态未知"
}

fun BlockReasonDomain.blockLabel(): String = when (this) {
    BlockReasonDomain.PROVIDER_OFFLINE -> "Provider 暂时离线"
    BlockReasonDomain.STORAGE_CAPACITY -> "等待释放存储空间"
    BlockReasonDomain.RETRY_BACKOFF -> "短暂退避后自动重试"
    BlockReasonDomain.LOCKED_CONFIGURATION_UNAVAILABLE -> "锁定的配置暂不可用"
    BlockReasonDomain.EXTERNAL_STATE_UNKNOWN -> "外部执行状态不确定"
    BlockReasonDomain.CONFIGURATION_INVALID -> "配置无效"
    BlockReasonDomain.UNKNOWN -> "未知原因"
}
