package com.clothesmodel.android.imports

import android.content.Context

object PendingImportRecovery {
    suspend fun resume(context: Context) {
        val database = PendingImportDatabase.build(context)
        try {
            val scheduler = PendingImportScheduler(context)
            database.pendingImports().recoverable().forEach { scheduler.enqueue(it.id) }
        } finally {
            database.close()
        }
    }
}
