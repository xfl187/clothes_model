package com.clothesmodel.android.imports

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class PendingImportWorker(
    context: Context,
    parameters: WorkerParameters,
) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val id = inputData.getString(IMPORT_ID) ?: return Result.failure()
        return when (LocalAssetUploader(applicationContext).ensureUploaded(id)) {
            is LocalAssetSyncResult.Ready -> Result.success()
            LocalAssetSyncResult.AuthenticationExpired -> Result.failure()
            is LocalAssetSyncResult.Failed -> Result.retry()
        }
    }

    companion object {
        const val IMPORT_ID = "import_id"
    }
}
