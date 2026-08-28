# ATLAS — PHASE 11 KNOWN LIMITATIONS

Same honesty standard as every prior phase's equivalent document: this
lists what's actually true about the current state, not what was
intended.

1. **Android is still never build-verified - this phase confirmed why,
   concretely, rather than repeating the claim unchanged.** No SDK, and
   `dl.google.com` / `repo.maven.apache.org` / `services.gradle.org` /
   `maven.google.com` all return `403 host_not_allowed`. Actually ran
   `./gradlew clean assembleDebug`: fails downloading the Gradle
   distribution itself, before Android SDK or any dependency resolution
   is reached. Every Android change across Phases 8-11 (now five new
   files, twelve modified files, six new/extended test files this phase
   alone) rests entirely on manual cross-referencing. This phase's own
   process caught two real mistakes in its own new code via that manual
   review (see Phase11_Report.md section 8) - a useful data point that
   the review process works, and an equally useful reminder that it
   isn't a substitute for a compiler.

2. **Proactive Suggestions (section 2) has never actually posted a
   notification on a device.** The full chain - WorkManager scheduling,
   Hilt injecting the worker's dependencies, the network call, the
   tracker's diff logic, `NotificationManagerCompat.notify()` - is
   reasoned through and unit-tested against fakes where testable
   (`ProactiveSuggestionsWorker` itself has no dedicated test - see
   below), but WorkManager's periodic scheduling, exact-alarm/Doze
   interaction, and the real Android 13+ permission dialog are runtime
   behaviors no JVM unit test exercises.

3. **`ProactiveSuggestionsWorker` itself has no unit test.** Its two
   collaborators (`ProactiveSuggestionTracker`'s diff logic is simple
   enough to reason about directly; the notification-posting path needs
   a real `Context`/`NotificationManager`, which this project's
   Robolectric-free JVM test setup can't provide) made a clean fake-based
   test impractical in the time available this phase. A real device test
   (`connectedAndroidTest`) is the natural way to cover this, once
   section 1 above is resolved.

4. **Voice-native confirmation's yes/no classifier is deliberately
   narrow.** `ConfirmationYesNoClassifier` only recognizes answers that
   *start* with a known phrase - "yes", "definitely, let's do that" would
   be UNCLEAR, not YES. This is an intentional simplicity/safety
   tradeoff (see the class's own doc comment), not an oversight, but it
   means real users will hit the "was that a yes or a no?" re-prompt for
   phrasings outside the recognized set more often than a more permissive
   (and less auditable) classifier would.

5. **The routine-time midnight-wraparound fix and the CUSTOM-recurrence
   nearest-day fix (both from the Phase 10 bug-fix pass) are unaffected
   by this phase** - listed here only to be explicit that this document
   is not re-certifying them; see `Phase10_BugFixes_Followup.md` for
   those.

6. **`datetime.utcnow()` is gone, but the backend is still not
   timezone-aware.** `utc_now()` (section 6) eliminates the deprecation
   warnings without touching the underlying naive-datetime storage model
   - every `DateTime` column is still plain `DateTime`, not
   `DateTime(timezone=True)`. A client in a non-UTC timezone still gets
   naive UTC timestamps and must convert client-side; this was true
   before this phase and remains true after it. Making the storage layer
   itself timezone-aware would need a coordinated Alembic migration and
   a decision about what the Android client actually sends - deliberately
   out of scope for a deprecation-warning cleanup.

7. **Section 7 (DeviceAction args type mismatch) remains open, now with
   a precise scope.** 14 read sites in `AutomationToolRouter.kt`, all
   `String?`-typed today. Not live (no backend tool puts a non-string
   value in `args`), so this is a latent risk, not an active bug.

8. **Section 3 (Routine creation UX) was not started this phase.**
   Routines are still creatable only via chat phrasing
   (`RoutineSkill`'s "create a routine called X with steps: a, b, c") -
   the Routines tab remains list/view/delete only.

9. **Section 8's re-verification is still static analysis, not a
   device.** The call-graph trace (single `sendMessage()` call site,
   gated by the stock Compose `AlertDialog`) is stronger evidence than
   Phase 10's original claim had, but "traced the code" and "tapped
   through it on a screen" are not the same confidence level, and this
   environment still can't provide the second one.

10. **The iterative agent loop (section 9) remains entirely unstarted**,
    exactly as instructed - not attempted given sections 3 and 7 weren't
    both complete with runway to spare.
