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
    val minutes = Duration.between(start, end).toMinutes().coerceAtLeast(0)
    return if (minutes < 60) "$minutes 分钟" else "${minutes / 60} 小时 ${minutes % 60} 分"
}

internal fun canCancelJob(state: JobStateDomain): Boolean = !state.isTerminal

internal fun canCancelCandidate(state: CandidateStateDomain): Boolean = !state.isTerminal

internal fun canRetryCandidate(state: CandidateStateDomain): Boolean =
    state == CandidateStateDomain.FAILED

internal fun needsAttentionActions(state: CandidateStateDomain): Boolean =
    state == CandidateStateDomain.NEEDS_ATTENTION

internal fun succeededCandidates(candidates: List<CandidateModel>): Int =
    candidates.count { it.state == CandidateStateDomain.SUCCEEDED }

internal fun failedCandidates(candidates: List<CandidateModel>): Int =
    candidates.count { it.state == CandidateStateDomain.FAILED }
