package com.clothesmodel.android.imports

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.room.testing.MigrationTestHelper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PendingImportMigrationTest {
    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        PendingImportDatabase::class.java,
    )

    @Test fun versionOneSchemaCanPersistRecoverableImport() {
        helper.createDatabase("pending-import-migration-test", 1).use { database ->
            database.execSQL(
                """INSERT INTO pending_imports
                    (id, stagedPath, displayName, contentType, assetKind, uploadId,
                     confirmedOffset, state, assetId)
                    VALUES ('one', '/private/one', 'one.png', 'image/png', 'person',
                            NULL, 0, 'staged', NULL)""".trimIndent(),
            )
            database.query("SELECT id FROM pending_imports WHERE id = 'one'").use { cursor ->
                assertTrue(cursor.moveToFirst())
            }
        }

        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val reopened = Room.databaseBuilder(
            context,
            PendingImportDatabase::class.java,
            "pending-import-migration-test",
        ).addMigrations(PendingImportDatabase.MIGRATION_1_2).build()
        try {
            val recovered = runBlocking { reopened.pendingImports().get("one") }
            assertEquals("/private/one", recovered?.stagedPath)
            assertEquals("staged", recovered?.state)
            assertEquals(null, recovered?.garmentCategory)
            assertEquals(null, recovered?.garmentSource)
        } finally {
            reopened.close()
            context.deleteDatabase("pending-import-migration-test")
        }
    }
}
