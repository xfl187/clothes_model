package com.clothesmodel.android.imports

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import java.io.File
import java.util.UUID

data class StagedImage(val file: File, val contentType: String)

class ImportStaging(private val context: Context) {
    fun copy(uri: Uri): StagedImage {
        val directory = File(context.filesDir, "pending-imports").apply { mkdirs() }
        val target = File(directory, "${UUID.randomUUID()}.stage")
        return when (context.contentResolver.getType(uri)?.lowercase()) {
            "image/png" -> {
                copyRaw(uri, target)
                StagedImage(target, "image/png")
            }
            "image/jpeg", "image/jpg" -> {
                copyRaw(uri, target)
                StagedImage(target, "image/jpeg")
            }
            // HEIC/WEBP and other formats are transcoded so the private backend,
            // which accepts JPEG/PNG only, can validate and normalize them.
            else -> {
                transcodeToJpeg(uri, target)
                StagedImage(target, "image/jpeg")
            }
        }
    }

    private fun copyRaw(uri: Uri, target: File) {
        context.contentResolver.openInputStream(uri).use { input ->
            requireNotNull(input) { "无法读取选择的图片" }
            target.outputStream().use(input::copyTo)
        }
    }

    private fun transcodeToJpeg(uri: Uri, target: File) {
        val bitmap = context.contentResolver.openInputStream(uri).use { input ->
            BitmapFactory.decodeStream(input)
        } ?: error("无法读取选择的图片")
        try {
            target.outputStream().use { output ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, 92, output)
            }
        } finally {
            bitmap.recycle()
        }
    }
}
