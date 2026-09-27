package com.clothesmodel.android.imports

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

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
    val garmentCategory: String? = null,
    val garmentSource: String? = null,
)

@Dao
interface PendingImportDao {
    @Query("SELECT * FROM pending_imports WHERE id = :id") suspend fun get(id: String): PendingImport?
    @Query("SELECT * FROM pending_imports WHERE state != 'completed'") suspend fun recoverable(): List<PendingImport>
    @Query("SELECT * FROM pending_imports") suspend fun all(): List<PendingImport>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun save(value: PendingImport)
    @Query("DELETE FROM pending_imports WHERE id = :id") suspend fun delete(id: String)
}

@Database(entities = [PendingImport::class], version = 2, exportSchema = true)
abstract class PendingImportDatabase : RoomDatabase() {
    abstract fun pendingImports(): PendingImportDao

    companion object {
        val MIGRATION_1_2: Migration = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN garmentCategory TEXT")
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN garmentSource TEXT")
            }
        }

        fun build(context: Context): PendingImportDatabase =
            Room.databaseBuilder(context, PendingImportDatabase::class.java, "pending-imports.db")
                .addMigrations(MIGRATION_1_2)
                .build()
    }
}
