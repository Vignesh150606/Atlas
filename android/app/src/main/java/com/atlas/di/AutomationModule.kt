package com.atlas.di

import com.atlas.automation.AccessibilityBridge
import com.atlas.automation.AccessibilityBridgeImpl
import com.atlas.automation.AndroidAppManager
import com.atlas.automation.AndroidClipboardTool
import com.atlas.automation.AndroidIntentTool
import com.atlas.automation.AndroidMediaSessionController
import com.atlas.automation.AndroidPermissionStatusChecker
import com.atlas.automation.AppManager
import com.atlas.automation.AutomationToolRouter
import com.atlas.automation.AutomationToolRouterImpl
import com.atlas.automation.ClipboardTool
import com.atlas.automation.IntentTool
import com.atlas.automation.MediaSessionControllerApi
import com.atlas.automation.NotificationBridge
import com.atlas.automation.NotificationBridgeImpl
import com.atlas.automation.PermissionStatusChecker
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation.
 *
 * Kept as its own module (rather than folded into AppModule) because it's
 * a cohesive, separately-landed unit of the app - mirrors how voice got
 * its own wiring surface in Phase 7. Same @Provides-object style as
 * AppModule for consistency across the codebase.
 */
@Module
@InstallIn(SingletonComponent::class)
object AutomationModule {

    @Provides
    @Singleton
    fun provideAccessibilityBridge(impl: AccessibilityBridgeImpl): AccessibilityBridge = impl

    @Provides
    @Singleton
    fun provideNotificationBridge(impl: NotificationBridgeImpl): NotificationBridge = impl

    @Provides
    @Singleton
    fun provideAppManager(impl: AndroidAppManager): AppManager = impl

    @Provides
    @Singleton
    fun provideMediaSessionController(impl: AndroidMediaSessionController): MediaSessionControllerApi = impl

    @Provides
    @Singleton
    fun provideClipboardTool(impl: AndroidClipboardTool): ClipboardTool = impl

    @Provides
    @Singleton
    fun provideIntentTool(impl: AndroidIntentTool): IntentTool = impl

    @Provides
    @Singleton
    fun provideAutomationToolRouter(impl: AutomationToolRouterImpl): AutomationToolRouter = impl

    @Provides
    @Singleton
    fun providePermissionStatusChecker(impl: AndroidPermissionStatusChecker): PermissionStatusChecker = impl
}
