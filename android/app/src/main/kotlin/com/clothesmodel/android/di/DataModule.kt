package com.clothesmodel.android.di

import android.content.Context
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.android.data.ApiServicesFactory
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.AuthenticationEvents
import com.clothesmodel.android.data.ConnectionApiServicesFactory
import com.clothesmodel.android.data.ContentRepository
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.ProviderRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

class ConnectionAuthenticationEvents(context: Context) : AuthenticationEvents {
    private val store = ConnectionStore(context.applicationContext, TokenVault(context))

    override suspend fun onAuthenticationExpired() {
        store.authenticationExpired()
    }
}

@Module
@InstallIn(SingletonComponent::class)
object DataModule {
    @Provides
    @Singleton
    fun provideAuthenticationEvents(
        @ApplicationContext context: Context,
    ): AuthenticationEvents = ConnectionAuthenticationEvents(context)

    @Provides
    @Singleton
    fun provideApiServicesFactory(
        @ApplicationContext context: Context,
        events: AuthenticationEvents,
    ): ApiServicesFactory = ConnectionApiServicesFactory(context, events)

    @Provides
    @Singleton
    fun provideAssetRepository(
        factory: ApiServicesFactory,
        events: AuthenticationEvents,
    ): AssetRepository = AssetRepository(factory, events)

    @Provides
    @Singleton
    fun provideJobRepository(
        factory: ApiServicesFactory,
        events: AuthenticationEvents,
    ): JobRepository = JobRepository(factory, events)

    @Provides
    @Singleton
    fun provideProviderRepository(
        factory: ApiServicesFactory,
        events: AuthenticationEvents,
    ): ProviderRepository = ProviderRepository(factory, events)

    @Provides
    @Singleton
    fun provideContentRepository(
        factory: ApiServicesFactory,
        events: AuthenticationEvents,
    ): ContentRepository = ContentRepository(factory, events)

    @Provides
    @Singleton
    fun provideImageLoader(content: ContentRepository): AuthenticatedImageLoader =
        AuthenticatedImageLoader(content = content)
}
