package com.clothesmodel.android.imports

import android.content.Context
import android.net.Uri
import java.io.File
import java.util.UUID

class ImportStaging(private val context: Context) {
    fun copy(uri: Uri): File {
        val directory = File(context.filesDir, "pending-imports").apply { mkdirs() }
        val target = File(directory, "${UUID.randomUUID()}.stage")
        context.contentResolver.openInputStream(uri).use { input ->
            requireNotNull(input) { "无法读取选择的图片" }
            target.outputStream().use(input::copyTo)
        }
        return target
    }
}
