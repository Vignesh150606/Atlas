package com.atlas.di

import com.atlas.api.AtlasApiService
import com.atlas.data.repository.ChatRepository
import com.atlas.data.repository.ChatRepositoryImpl
import com.atlas.data.repository.MemoryRepository
import com.atlas.data.repository.MemoryRepositoryImpl
import com.atlas.data.repository.KnowledgeRepository
import com.atlas.data.repository.KnowledgeRepositoryImpl
import com.atlas.data.repository.PersonalAssistantRepository
import com.atlas.data.repository.PersonalAssistantRepositoryImpl
import com.atlas.data.repository.VoiceRepository
import com.atlas.voice.AndroidSpeechToTextEngine
import com.atlas.voice.AndroidTextToSpeechEngine
import com.atlas.voice.AndroidAudioSessionManager
import com.atlas.voice.AudioSessionManager
import com.atlas.voice.ConversationAudioController
import com.atlas.voice.SpeechToTextEngine
import com.atlas.voice.TextToSpeechEngine
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    // Phase 12 (docs/MASTER_PLAN.md #2.1): Retrofit needs *some* syntactically
    // valid baseUrl to build against, but the real target is decided
    // per-request by BaseUrlInterceptor from ServerConfigStore - this
    // placeholder host is never actually resolved or connected to (see
    // BaseUrlInterceptor's doc comment). It deliberately does NOT carry any
    // real address - see ServerConfigStore.DEFAULT_BASE_URL for the actual
    // functional default.
    private const val RETROFIT_PLACEHOLDER_BASE_URL = "http://retrofit-placeholder.invalid/api/v1/"

    @Provides
    @Singleton
    fun provideOkHttpClient(
        apiKeyInterceptor: ApiKeyInterceptor,
        baseUrlInterceptor: BaseUrlInterceptor,
    ): OkHttpClient {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            // Phase 12 / SECURITY_PLAN.md S3: full request/response bodies -
            // chat content, memories, and the X-API-Key header - were being
            // logged unconditionally, including in release builds. BODY
            // logging is a debug-only convenience now; release builds log
            // nothing via this interceptor.
            level = if (com.atlas.BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY else HttpLoggingInterceptor.Level.NONE
        }
        return OkHttpClient.Builder()
            // Order matters: BaseUrlInterceptor must run before the request
            // reaches ApiKeyInterceptor/logging so both act on the real
            // target, and before the logging interceptor so a debug build
            // logs the URL actually being called.
            .addInterceptor(baseUrlInterceptor)
            .addInterceptor(apiKeyInterceptor)
            .addInterceptor(loggingInterceptor)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl(RETROFIT_PLACEHOLDER_BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideAtlasApiService(retrofit: Retrofit): AtlasApiService {
        return retrofit.create(AtlasApiService::class.java)
    }

    @Provides
    @Singleton
    fun provideChatRepository(apiService: AtlasApiService): ChatRepository {
        return ChatRepositoryImpl(apiService)
    }

    @Provides
    @Singleton
    fun provideMemoryRepository(apiService: AtlasApiService): MemoryRepository {
        return MemoryRepositoryImpl(apiService)
    }

    @Provides
    @Singleton
    fun provideKnowledgeRepository(apiService: AtlasApiService): KnowledgeRepository {
        return KnowledgeRepositoryImpl(apiService)
    }

    // Phase 10: Personal Assistant & Proactive Intelligence
    @Provides
    @Singleton
    fun providePersonalAssistantRepository(apiService: AtlasApiService): PersonalAssistantRepository {
        return PersonalAssistantRepositoryImpl(apiService)
    }

    @Provides
    @Singleton
    fun provideSpeechToTextEngine(engine: AndroidSpeechToTextEngine): SpeechToTextEngine = engine

    @Provides
    @Singleton
    fun provideTextToSpeechEngine(engine: AndroidTextToSpeechEngine): TextToSpeechEngine = engine

    // Phase 11: same pattern as the two engine bindings above - narrows
    // ApiKeyStore (read+write, backed by SharedPreferences) down to the
    // read-only ApiKeyProvider interface ApiKeyInterceptor actually
    // needs, so interceptor tests can fake just that one method.
    @Provides
    @Singleton
    fun provideApiKeyProvider(store: com.atlas.data.local.ApiKeyStore): com.atlas.data.local.ApiKeyProvider = store

    // Phase 12: same pattern - ServerConfigStore (read+write) narrowed to
    // the read-only ServerConfigProvider BaseUrlInterceptor needs.
    @Provides
    @Singleton
    fun provideServerConfigProvider(store: com.atlas.data.local.ServerConfigStore): com.atlas.data.local.ServerConfigProvider = store

    // Phase 8 stabilization: binds the interface extracted from what used
    // to be a directly-injected concrete AudioSessionManager class - see
    // the doc comment on the AudioSessionManager interface in
    // voice/AudioSessionManager.kt for why.
    @Provides
    @Singleton
    fun provideAudioSessionManager(engine: AndroidAudioSessionManager): AudioSessionManager = engine

    @Provides
    @Singleton
    fun provideVoiceRepository(controller: ConversationAudioController): VoiceRepository = controller
}
