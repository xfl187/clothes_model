package com.clothesmodel.android.results

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.core.content.FileProvider
import java.io.File
import java.util.UUID

sealed interface DownloadResult {
    data class Success(val uri: Uri) : DownloadResult
    data class Failure(val message: String) : DownloadResult
}

fun downloadToMediaStore(
    context: Context,
    assetId: UUID,
    bytes: ByteArray,
): DownloadResult {
    val resolver = context.contentResolver
    val values = ContentValues().apply {
        put(MediaStore.Images.Media.DISPLAY_NAME, "clothes-model-$assetId.jpg")
        put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            put(
                MediaStore.Images.Media.RELATIVE_PATH,
                "${Environment.DIRECTORY_PICTURES}/ClothesModel",
            )
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
    }
    val collection = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
    } else {
        MediaStore.Images.Media.EXTERNAL_CONTENT_URI
    }
    return try {
        val uri = resolver.insert(collection, values)
            ?: return DownloadResult.Failure("无法创建图库条目。")
        resolver.openOutputStream(uri)?.use { it.write(bytes) }
            ?: return DownloadResult.Failure("无法写入图库。")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val done = ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }
            resolver.update(uri, done, null, null)
        }
        DownloadResult.Success(uri)
    } catch (error: Exception) {
        DownloadResult.Failure("保存到图库失败。")
    }
}

fun shareResultIntent(
    context: Context,
    assetId: UUID,
    bytes: ByteArray,
): Intent {
    val directory = File(context.cacheDir, "shared").apply { mkdirs() }
    val file = File(directory, "$assetId.jpg")
    file.writeBytes(bytes)
    val uri = FileProvider.getUriForFile(
        context,
        "${context.packageName}.fileprovider",
        file,
    )
    return Intent(Intent.ACTION_SEND).apply {
        type = "image/jpeg"
        putExtra(Intent.EXTRA_STREAM, uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
}
