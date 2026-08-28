package com.atlas.proactive

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * Phase 11 section 2. Called once from AtlasApplication.onCreate().
 * ExistingPeriodicWorkPolicy.KEEP - not REPLACE - so re-enqueuing on
 * every process start (which onCreate() runs on) doesn't reset an
 * already-scheduled job's timing; WorkManager persists the schedule
 * across process death on its own.
 */
object ProactiveSuggestionsScheduler {
    private const val UNIQUE_WORK_NAME = "atlas_proactive_suggestions"

    // Mission brief section 2: "roughly every 15-30 minutes, per the
    // Phase 10 mission brief's own suggested cadence" - using the upper
    // end (30 min) to stay clearly inside WorkManager's minimum periodic
    // interval (15 min) with margin, and per Phase 10's "no battery
    // drain" constraint.
    private const val INTERVAL_MINUTES = 30L

    fun schedule(context: Context) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val request = PeriodicWorkRequestBuilder<ProactiveSuggestionsWorker>(INTERVAL_MINUTES, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .build()

        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            UNIQUE_WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            request
        )
    }
}
