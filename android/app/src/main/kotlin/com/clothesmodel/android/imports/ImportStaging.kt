package com.clothesmodel.android.imports

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.UUID

data class StagedImage(
    val file: File,
    val contentType: String,
    val sha256: String,
    val sizeBytes: Long,
)

class ImportStaging(private val context: Context) {
    fun copy(uri: Uri): StagedImage {
        val directory = File(context.filesDir, "local-assets").apply { mkdirs() }
        val id = UUID.randomUUID().toString()
        val temporary = File(directory, "$id.tmp")
        val target = File(directory, "$id.image")
        val contentType = when (context.contentResolver.getType(uri)?.lowercase()) {
            "image/png" -> {
                copyRaw(uri, temporary)
                "image/png"
            }
            "image/jpeg", "image/jpg" -> {
                copyRaw(uri, temporary)
                "image/jpeg"
            }
            // HEIC/WEBP and other formats are transcoded so the private backend,
            // which accepts JPEG/PNG only, can validate and normalize them.
            else -> {
                transcodeToJpeg(uri, temporary)
                "image/jpeg"
            }
        }
        FileOutputStream(temporary, true).use { it.fd.sync() }
        check(temporary.renameTo(target)) { "无法保存所选图片" }
        val digest = target.inputStream().use { input ->
            MessageDigest.getInstance("SHA-256").digest(input.readBytes())
                .joinToString("") { "%02x".format(it) }
        }
        return StagedImage(target, contentType, digest, target.length())
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
