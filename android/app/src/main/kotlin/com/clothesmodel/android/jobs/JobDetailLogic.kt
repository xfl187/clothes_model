package com.clothesmodel.android.jobs

import com.clothesmodel.android.data.CandidateModel
import com.clothesmodel.android.data.CandidateStateDomain
import com.clothesmodel.android.data.JobStateDomain
import java.time.Duration
import java.time.OffsetDateTime

internal fun candidateStateLabel(state: CandidateStateDomain): String = when (state) {
    CandidateStateDomain.QUEUED -> "已排队"
    CandidateStateDomain.WAITING_PROVIDER -> "等待 Provider"
    CandidateStateDomain.PREPARING -> "正在准备"
    CandidateStateDomain.RUNNING -> "正在生成"
    CandidateStateDomain.NEEDS_ATTENTION -> "需要人工处理"
    CandidateStateDomain.SUCCEEDED -> "成功"
    CandidateStateDomain.FAILED -> "失败"
    CandidateStateDomain.CANCELLED -> "已取消"
    CandidateStateDomain.UNKNOWN -> "状态未知"
}

internal fun formatElapsed(start: OffsetDateTime, end: OffsetDateTime): String {
    val duration = Duration.between(start, end).coerceAtLeast(Duration.ZERO)
    val seconds = duration.seconds
    if (seconds < 60) return "$seconds 秒"
    val minutes = duration.toMinutes()
    return if (minutes < 60) "$minutes 分钟" else "${minutes / 60} 小时 ${minutes % 60} 分"
}

internal fun canCancelJob(state: JobStateDomain): Boolean = !state.isTerminal

internal fun canCancelCandidate(state: CandidateStateDomain): Boolean = !state.isTerminal

internal fun canRetryCandidate(state: CandidateStateDomain): Boolean =
    state == CandidateStateDomain.FAILED

internal fun needsAttentionActions(state: CandidateStateDomain): Boolean =
    state == CandidateStateDomain.NEEDS_ATTENTION

internal fun succeededCandidates(candidates: List<CandidateModel>): Int =
    candidates.count { it.isCurrentAttempt && it.state == CandidateStateDomain.SUCCEEDED }

internal fun failedCandidates(candidates: List<CandidateModel>): Int =
    candidates.count { it.isCurrentAttempt && it.state == CandidateStateDomain.FAILED }

internal fun completedCandidates(candidates: List<CandidateModel>): Int =
    candidates.count { it.isCurrentAttempt && it.state.isTerminal }

private val CandidateModel.isCurrentAttempt: Boolean
    get() = supersededByJobItemId == null

internal fun isProgressActive(state: JobStateDomain): Boolean = when (state) {
    JobStateDomain.QUEUED,
    JobStateDomain.WAITING_PROVIDER,
    JobStateDomain.PREPARING,
    JobStateDomain.RUNNING,
    -> true

    else -> false
}

internal fun progressStageLabel(state: JobStateDomain): String? = when (state) {
    JobStateDomain.QUEUED -> "阶段 1/3 · 已排队"
    JobStateDomain.WAITING_PROVIDER -> "等待 Provider · 恢复后自动继续"
    JobStateDomain.PREPARING -> "阶段 2/3 · 正在准备输入"
    JobStateDomain.RUNNING -> "阶段 3/3 · 正在生成"
    else -> null
}
