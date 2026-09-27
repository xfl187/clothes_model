package com.clothesmodel.android.connection

import java.net.URI

object ServerEndpoint {
    fun normalize(input: String, allowedHttpHosts: Set<String> = emptySet()): String {
        val candidate = input.trim().let { if ("://" in it) it else "https://$it" }
        val uri = runCatching { URI(candidate) }.getOrElse { error("服务器地址无效") }
        require(uri.userInfo == null && uri.query == null && uri.fragment == null) { "服务器地址无效" }
        require(!uri.host.isNullOrBlank()) { "服务器地址无效" }
        require(uri.scheme == "https" || (uri.host in allowedHttpHosts && uri.scheme == "http")) {
            "必须使用 HTTPS"
        }
        return URI(uri.scheme.lowercase(), null, uri.host.lowercase(), uri.port, uri.path.trimEnd('/'), null, null).toString().trimEnd('/') + "/"
    }
}
