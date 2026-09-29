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
    val lastError: String? = null,
    val updatedAt: Long = 0,
    val sha256: String? = null,
    val sizeBytes: Long = 0,
    val serverInstanceId: String? = null,
    val ownerScopeId: String? = null,
    val favorite: Boolean = false,
)

@Dao
interface PendingImportDao {
    @Query("SELECT * FROM pending_imports WHERE id = :id") suspend fun get(id: String): PendingImport?
    @Query("SELECT * FROM pending_imports WHERE state != 'completed'") suspend fun recoverable(): List<PendingImport>
    @Query("SELECT * FROM pending_imports") suspend fun all(): List<PendingImport>
    @Query("SELECT * FROM pending_imports WHERE assetKind = :kind ORDER BY updatedAt DESC")
    suspend fun byKind(kind: String): List<PendingImport>
    @Query(
        "SELECT * FROM pending_imports WHERE assetKind = :kind AND " +
            "(:serverId IS NULL OR serverInstanceId IS NULL OR serverInstanceId = :serverId) AND " +
            "(:ownerId IS NULL OR ownerScopeId IS NULL OR ownerScopeId = :ownerId) " +
            "ORDER BY updatedAt DESC",
    )
    suspend fun byKindForOwner(kind: String, serverId: String?, ownerId: String?): List<PendingImport>
    @Query("SELECT * FROM pending_imports WHERE assetId = :assetId LIMIT 1")
    suspend fun byServerAssetId(assetId: String): PendingImport?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun save(value: PendingImport)
    @Query("DELETE FROM pending_imports WHERE id = :id") suspend fun delete(id: String)
    @Query("UPDATE pending_imports SET favorite = :favorite, updatedAt = :updatedAt WHERE id = :id")
    suspend fun setFavorite(id: String, favorite: Boolean, updatedAt: Long)
}

@Database(entities = [PendingImport::class], version = 5, exportSchema = true)
abstract class PendingImportDatabase : RoomDatabase() {
    abstract fun pendingImports(): PendingImportDao

    companion object {
        val MIGRATION_1_2: Migration = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN garmentCategory TEXT")
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN garmentSource TEXT")
            }
        }

        val MIGRATION_2_3: Migration = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN lastError TEXT")
                db.execSQL(
                    "ALTER TABLE pending_imports ADD COLUMN updatedAt INTEGER NOT NULL DEFAULT 0",
                )
            }
        }

        val MIGRATION_3_4: Migration = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN sha256 TEXT")
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN sizeBytes INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN serverInstanceId TEXT")
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN ownerScopeId TEXT")
            }
        }

        val MIGRATION_4_5: Migration = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE pending_imports ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0")
            }
        }

        fun build(context: Context): PendingImportDatabase =
            Room.databaseBuilder(context, PendingImportDatabase::class.java, "pending-imports.db")
                .addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5)
                .build()
    }
}
