package com.clothesmodel.android.imports

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase

@Entity(tableName = "pending_imports")
data class PendingImport(
    @PrimaryKey val id: String,
    val stagedPath: String,
    val displayName: String,
    val contentType: String,
    val assetKind: String,
    val uploadId: String? = null,
    val confirmedOffset: Long = 0,
    val state: String = "staged",
    val assetId: String? = null,
)

@Dao
interface PendingImportDao {
    @Query("SELECT * FROM pending_imports WHERE id = :id") suspend fun get(id: String): PendingImport?
    @Query("SELECT * FROM pending_imports WHERE state != 'completed'") suspend fun recoverable(): List<PendingImport>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun save(value: PendingImport)
    @Query("DELETE FROM pending_imports WHERE id = :id") suspend fun delete(id: String)
}

@Database(entities = [PendingImport::class], version = 1, exportSchema = true)
abstract class PendingImportDatabase : RoomDatabase() {
    abstract fun pendingImports(): PendingImportDao
}
