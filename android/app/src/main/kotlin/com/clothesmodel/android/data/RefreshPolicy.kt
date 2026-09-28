package com.clothesmodel.android.data

object RefreshPolicy {
    val pollableStates: Set<JobStateDomain> = setOf(
        JobStateDomain.QUEUED,
        JobStateDomain.WAITING_PROVIDER,
        JobStateDomain.PREPARING,
        JobStateDomain.RUNNING,
    )

    fun shouldPoll(state: JobStateDomain): Boolean = state in pollableStates
}
