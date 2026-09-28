package com.clothesmodel.android.data

import java.io.File
import java.util.LinkedHashMap
import java.util.UUID

sealed interface ImageResult {
    data class Loaded(val bytes: ByteArray) : ImageResult {
        override fun equals(other: Any?): Boolean =
            other is Loaded && bytes.contentEquals(other.bytes)

        override fun hashCode(): Int = bytes.contentHashCode()
    }

    data class Unavailable(val problem: ProblemModel) : ImageResult

    data object DeletedContent : ImageResult

    data object AuthenticationExpired : ImageResult
}

interface ImageCache {
    fun get(key: UUID): ByteArray?

    fun put(key: UUID, bytes: ByteArray)

    fun evict(key: UUID)

    fun clear()
}

class BoundedMemoryImageCache(private val maxBytes: Long) : ImageCache {
    private val entries = LinkedHashMap<UUID, ByteArray>(16, 0.75f, true)
    private var sizeBytes = 0L

    @Synchronized
    override fun get(key: UUID): ByteArray? = entries[key]

    @Synchronized
    override fun put(key: UUID, bytes: ByteArray) {
        entries.remove(key)?.let { sizeBytes -= it.size }
        entries[key] = bytes
        sizeBytes += bytes.size
        val iterator = entries.entries.iterator()
        while (sizeBytes > maxBytes && iterator.hasNext()) {
            val oldest = iterator.next()
            sizeBytes -= oldest.value.size
            iterator.remove()
        }
    }

    @Synchronized
    override fun evict(key: UUID) {
        entries.remove(key)?.let { sizeBytes -= it.size }
    }

    @Synchronized
    override fun clear() {
        entries.clear()
        sizeBytes = 0
    }
}

class FileImageCache(
    private val directory: File,
    private val maxBytes: Long,
) : ImageCache {
    override fun get(key: UUID): ByteArray? {
        val file = fileFor(key)
        if (!file.isFile) return null
        file.setLastModified(System.currentTimeMillis())
        return runCatching { file.readBytes() }.getOrNull()
    }

    override fun put(key: UUID, bytes: ByteArray) {
        directory.mkdirs()
        runCatching { fileFor(key).writeBytes(bytes) }
        trim()
    }

    override fun evict(key: UUID) {
        runCatching { fileFor(key).delete() }
    }

    override fun clear() {
        runCatching { directory.listFiles()?.forEach(File::delete) }
    }

    private fun fileFor(key: UUID): File = File(directory, key.toString())

    private fun trim() {
        val files = directory.listFiles()?.filter(File::isFile) ?: return
        var total = files.sumOf { it.length() }
        if (total <= maxBytes) return
        files.sortedBy(File::lastModified).forEach { file ->
            if (total <= maxBytes) return
            total -= file.length()
            file.delete()
        }
    }
}

fun interface ContentFetcher {
    suspend fun fetch(assetId: UUID): Outcome<ByteArray>
}

class AuthenticatedImageLoader(
    private val content: ContentFetcher,
    private val memoryCache: ImageCache = BoundedMemoryImageCache(16L * 1024 * 1024),
    private val diskCache: ImageCache? = null,
) {
    suspend fun load(assetId: UUID): ImageResult {
        memoryCache.get(assetId)?.let { return ImageResult.Loaded(it) }
        diskCache?.get(assetId)?.let {
            memoryCache.put(assetId, it)
            return ImageResult.Loaded(it)
        }
        return when (val outcome = content.fetch(assetId)) {
            is Outcome.Success -> {
                memoryCache.put(assetId, outcome.value)
                diskCache?.put(assetId, outcome.value)
                ImageResult.Loaded(outcome.value)
            }

            is Outcome.Problem -> if (outcome.problem.status == 404) {
                ImageResult.DeletedContent
            } else {
                ImageResult.Unavailable(outcome.problem)
            }

            Outcome.AuthenticationExpired -> ImageResult.AuthenticationExpired
        }
    }

    fun evict(assetId: UUID) {
        memoryCache.evict(assetId)
        diskCache?.evict(assetId)
    }
}
