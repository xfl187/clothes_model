package com.clothesmodel.android.assets

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.ImageResult
import com.clothesmodel.android.ui.theme.LocalAtelierTokens
import java.util.UUID

@Composable
fun AssetImage(
    assetId: UUID,
    loader: AuthenticatedImageLoader,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    deletedLabel: String = "素材已删除",
    contentScale: ContentScale = ContentScale.Crop,
) {
    val result by produceState<ImageResult?>(initialValue = null, assetId) {
        value = loader.load(assetId)
    }
    val loaded = result
    when (loaded) {
        null -> ImagePlaceholder("正在加载", modifier)
        ImageResult.DeletedContent -> ImagePlaceholder(deletedLabel, modifier)
        ImageResult.AuthenticationExpired -> ImagePlaceholder("需要重新认证", modifier)
        is ImageResult.Unavailable -> ImagePlaceholder("图片暂不可用", modifier)
        is ImageResult.Loaded -> {
            val bitmap = remember(loaded.bytes) {
                BitmapFactory.decodeByteArray(loaded.bytes, 0, loaded.bytes.size)
            }
            if (bitmap == null) {
                ImagePlaceholder("图片暂不可用", modifier)
            } else {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = contentDescription,
                    contentScale = contentScale,
                    modifier = modifier.fillMaxSize(),
                )
            }
        }
    }
}

@Composable
private fun ImagePlaceholder(label: String, modifier: Modifier) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(LocalAtelierTokens.current.mist)
            .padding(8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
