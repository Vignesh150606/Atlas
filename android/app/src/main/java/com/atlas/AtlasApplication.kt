package com.atlas

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.atlas.proactive.ProactiveSuggestionsScheduler
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class AtlasApplication : Application(), Configuration.Provider {

    // Phase 11 section 2: needed so WorkManager can construct
    // ProactiveSuggestionsWorker with its Hilt-injected dependencies
    // (PersonalAssistantRepository, ProactiveSuggestionTracker) - the
    // default WorkManager factory only knows how to call a no-arg
    // constructor, which @HiltWorker classes don't have.
    @Inject lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun onCreate() {
        super.onCreate()
        // WorkManager's default auto-initializer is disabled in
        // AndroidManifest.xml (required so the Configuration above -
        // with the Hilt worker factory - is actually the one used,
        // instead of WorkManager silently self-initializing with the
        // default factory first). Scheduling here means WorkManager
        // initializes on-demand at this first getInstance() call.
        ProactiveSuggestionsScheduler.schedule(this)
    }
}
