package com.clothesmodel.android.navigation

object Destinations {
    const val ARG_ASSET_ID = "assetId"
    const val ARG_JOB_ID = "jobId"
    const val ARG_CANDIDATE_ID = "candidateId"
    const val ARG_REAUTH = "reauth"

    const val CONNECTION = "connection?$ARG_REAUTH={$ARG_REAUTH}"
    const val MAIN = "main"
    const val HOME = "home"
    const val ASSETS = "assets"
    const val HISTORY = "history"
    const val ASSET_DETAIL = "assets/{$ARG_ASSET_ID}"
    const val CREATE = "create"
    const val JOB_DETAIL = "jobs/{$ARG_JOB_ID}"
    const val RESULTS = "jobs/{$ARG_JOB_ID}/results"
    const val COMPARE = "jobs/{$ARG_JOB_ID}/compare/{$ARG_CANDIDATE_ID}"
    const val MASK = "jobs/{$ARG_JOB_ID}/mask/{$ARG_CANDIDATE_ID}"

    fun connection(reauth: Boolean = false): String = "connection?$ARG_REAUTH=$reauth"

    fun assetDetail(assetId: String): String = "assets/$assetId"

    fun jobDetail(jobId: String): String = "jobs/$jobId"

    fun results(jobId: String): String = "jobs/$jobId/results"

    fun compare(jobId: String, candidateId: String): String =
        "jobs/$jobId/compare/$candidateId"

    fun mask(jobId: String, candidateId: String): String = "jobs/$jobId/mask/$candidateId"

    val tabRoutes: List<Pair<String, String>> = listOf(
        HOME to "首页",
        ASSETS to "素材",
        HISTORY to "历史",
    )
}
