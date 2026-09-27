package com.clothesmodel.android.imports

import android.content.Context
import androidx.room.Room

object PendingImportRecovery {
    suspend fun resume(context: Context) {
        val database = Room.databaseBuilder(
            context,
            PendingImportDatabase::class.java,
            "pending-imports.db",
        ).build()
        try {
            val scheduler = PendingImportScheduler(context)
            database.pendingImports().recoverable().forEach { scheduler.enqueue(it.id) }
        } finally {
            database.close()
        }
    }
}
