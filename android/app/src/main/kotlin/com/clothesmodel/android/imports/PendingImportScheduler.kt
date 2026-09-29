package com.clothesmodel.android.imports

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import java.util.concurrent.TimeUnit

class PendingImportScheduler(private val context: Context) {
    fun enqueue(importId: String) {
        val request = OneTimeWorkRequestBuilder<PendingImportWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .setInputData(workDataOf(PendingImportWorker.IMPORT_ID to importId))
            .addTag(AUTHENTICATED_UPLOAD_TAG)
            .addTag(importTag(importId))
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("pending-import-$importId", ExistingWorkPolicy.KEEP, request)
    }

    fun cancel(importId: String) = WorkManager.getInstance(context).cancelUniqueWork("pending-import-$importId")

    companion object {
        const val AUTHENTICATED_UPLOAD_TAG = "authenticated-pending-upload"

        fun importTag(importId: String): String = "pending-import-id:$importId"
    }
}
