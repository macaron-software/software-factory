# NARABAYBY — SAFe EPIC → STORY → FUNCTION MAPPING

## STRATEGIC THEMES → EPICS

### ST-1: Evidence-Based Baby Tracking

**Epic**: EPI-001-EVIDENCE-TRACKING
**Hypothesis**: Parents need clinically-valid data, not opinions

| Story | Component | Implementation | Functions |
|-------|-----------|-----------------|-----------|
| **US-001**: Log baby data | models/ | 8 data types | add_baby, log_feed, start_sleep, log_diaper, log_growth, add_milestone |
| **US-002**: Calculate daily summaries | engines/ | Aggregation logic | feeding_summary_json, sleep_summary_json, diaper_summary_json, daily_summary_json |
| **US-003**: Alert on AAP thresholds | engines/alerts | Threshold checks | DiaperEngine::check_threshold, AlertEngine::check_all |
| **US-004**: Source every alert | evidence/ | Citation metadata | Alert.source_id, Alert.source_url |

**Acceptance Criteria**:
- ✅ Every threshold cites a peer-reviewed source
- ✅ AAP diaper thresholds Day1-Day7 exact
- ✅ Wake window alerts based on observational data
- ✅ No-feed alert after 24h
- ✅ Alerts include source URL

---

### ST-2: Privacy-by-Design (Local-First, E2E Encrypted)

**Epic**: EPI-002-PRIVACY-DESIGN
**Hypothesis**: Parents will adopt app only if they own their data

| Story | Component | Implementation | Functions |
|-------|-----------|-----------------|-----------|
| **US-101**: Encrypt data at rest | crypto/ | AES-256-GCM | encrypt(), decrypt() |
| **US-102**: Derive key from passphrase | crypto/ | Argon2id KDF | derive_key() |
| **US-103**: Secure key storage | crypto/ | Zeroization | zeroize_key() |
| **US-104**: Zero-knowledge sync backend | backend/ | gRPC + encrypted blobs | Push(), Pull() |
| **US-105**: Require JWT for sync | backend/ | JWT auth | validate_jwt(), extract_device_id() |

**Acceptance Criteria**:
- ✅ All local data encrypted with AES-256-GCM
- ✅ No plaintext stored on device
- ✅ Server never sees plaintext (even during sync)
- ✅ JWT expires after 90 days
- ✅ Rate limiting on register/push/pull

---

### ST-3: Multi-Platform, One Core

**Epic**: EPI-003-MULTI-PLATFORM
**Hypothesis**: Single Rust core → iOS/Android/Web parity

| Story | Component | Implementation | Bindings |
|-------|-----------|-----------------|----------|
| **US-201**: iOS app via UniFFI | uniffi_api.rs | Swift bindings | BabyCore (cdylib) |
| **US-202**: Android app via UniFFI | uniffi_api.rs | Kotlin bindings | BabyCore (JNI) |
| **US-203**: Web app via WASM | wasm.rs | JavaScript bindings | BabyCore (wasm-pack) |
| **US-204**: Feature-flag platform code | lib.rs | #[cfg(feature)] | native vs wasm |

**Acceptance Criteria**:
- ✅ iOS passes XCode build test
- ✅ Android passes gradle build test
- ✅ Web runs in browser sandbox
- ✅ Feature flags compile-time eliminate platform code
- ✅ Core logic 100% shared

---

### ST-4: Parental Wellness & PPD Detection (PI-2)

**Epic**: EPI-004-PARENTAL-WELLNESS
**Hypothesis**: Tracking parental health improves outcomes

| Story | Component | Implementation | Functions |
|-------|-----------|-----------------|-----------|
| **US-301**: Log parental mood | models/wellness.rs | mood: String | log_wellness() |
| **US-302**: Calculate EPDS score | engines/wellness.rs (NEW) | EPDS algorithm | calculate_epds() |
| **US-303**: Alert on PPD indicators | engines/alerts.rs | EPDS ≥13 threshold | check_ppd_alert() |
| **US-304**: Track caregiver sleep/nutrition | models/wellness.rs | hours, meals_count | log_wellness() |

**Acceptance Criteria**:
- ✅ EPDS validated (Edinburgh Postnatal Depression Screen)
- ✅ PPD alert triggered at ≥13 (evidence-based cutoff)
- ✅ Caregiver wellness separate from baby data
- ✅ Multi-caregiver support
- ✅ Privacy: data not shared without consent

---

### ST-5: Continuous Quality (Adversarial Validation)

**Epic**: EPI-005-QUALITY
**Hypothesis**: Adversarial testing catches edge cases before production

| Story | Component | Implementation | Scope |
|-------|-----------|-----------------|-------|
| **US-401**: Unit test full workflow | tests/ | test_full_workflow() | Core logic |
| **US-402**: Test edge cases (dates, UUIDs) | tests/ | test_*_roundtrip() | Serialization |
| **US-403**: JWT validation tests | tests/ | test_jwt_* | Auth |
| **US-404**: Rate limiter tests | tests/ | test_rate_limiter_* | Security |

**Acceptance Criteria**:
- ✅ 90%+ code coverage
- ✅ All public functions tested
- ✅ Security paths tested (auth rejection, rate limit)
- ✅ Adversarial review before merge

---

---

## PROGRAM INCREMENT 1 (PI-1): Foundation + Core MVP

**Timeframe**: Weeks 1-6
**Hypothesis**: Parents adopt app if simple, reliable, no-account-required

### I-1.1: Rust Core Foundation

**Feature**: Create `narabayby-core` library with models + storage

```
User Story: "As a developer, I can build a Rust library that models baby data"

Acceptance Criteria:
✅ Baby struct with id, name, birth_date, sex, created_at
✅ Feed types: Breast (side, duration), Bottle (content, ml), Solid, Pumping
✅ Sleep types: Nap, Night
✅ Diaper types: Wet, Dirty, Mixed, Dry
✅ Growth: weight, height, head_cm optional
✅ Milestone: domain (Motor, Social, Language, Cognitive), expected_age
✅ All structs derive Serialize, Deserialize
✅ Unit tests for model roundtrip

Tasks:
- models/baby.rs: Baby::new(), age_days(), age_months()
- models/feed.rs: FeedType enum, Feed struct + constructors
- models/sleep.rs: Sleep struct, start(), end(), duration_secs()
- models/diaper.rs: Diaper struct, is_wet()
- models/growth.rs: GrowthEntry with optional fields
- models/milestone.rs: Milestone with CDC source
- storage/schema.rs: SQLite schema V1
- storage/db.rs: CRUD for all entities

Functions Implemented:
- Baby: new(), age_days(), age_months()
- Feed: new_breast(), new_bottle(), breast_side()
- Sleep: start(), end(), duration_secs(), is_active()
- Diaper: new(), is_wet()
- GrowthEntry: new()
- Milestone: new(), is_achieved()
- Database: insert_*, get_*, list_*, update_*, delete_*
```

---

### I-1.2: Engines + Thresholds

**Feature**: Implement business logic engines with AAP/WHO/CDC thresholds

```
User Story: "As a parent, I want the app to calculate daily summaries and alert me on medical concerns"

Acceptance Criteria:
✅ Feeding summary: counts by type, totals
✅ Sleep summary: separate nap vs night, total hours
✅ Diaper summary: count by type, rash tracking
✅ Alerts: AAP diaper thresholds Day1-7+
✅ Alerts: Extended wake window (>2h for <3mo)
✅ Alerts: No feed in 24h
✅ Every alert includes source URL
✅ Unit tests for each engine

Tasks:
- engines/feeding.rs: log_breast(), log_bottle(), last_side(), daily_summary()
- engines/sleep.rs: start(), end(), daily_summary(), wake_time_secs()
- engines/diaper.rs: log(), daily_summary(), check_threshold()
- engines/alerts.rs: check_all() → Vec<Alert>
- evidence/thresholds.rs: AAP constants (Day1=1, Day2=2, ..., Week1+=6)
- evidence/sources.rs: Source URLs for AAP, WHO, CDC

Functions Implemented:
- FeedingEngine: log_breast(), log_bottle(), last_side(), daily_summary(), summary_since()
- SleepEngine: start(), end(), daily_summary(), wake_time_secs()
- DiaperEngine: log(), daily_summary(), check_threshold()
- AlertEngine: check_all()
  ├─ Diaper threshold alert (Urgent if 0 wet, Warning if low)
  ├─ No-feed alert (24h, Warning)
  └─ Wake window alert (Info)
```

---

### I-1.3: iOS MVP (SwiftUI)

**Feature**: One-screen iOS app that logs and displays events

```
User Story: "As an iOS parent, I can log feeding, sleep, diaper in one tap and see timeline"

Acceptance Criteria:
✅ Home screen with timeline (latest 24h)
✅ One-tap logging: Feed (Breast/Bottle), Sleep (Nap/Night), Diaper (4 types)
✅ Next breast side recommendation displayed
✅ Daily summary card (feeds, sleep, diapers)
✅ Alerts section (if any)
✅ All data stored locally (no account)
✅ E2E test: add baby → log feed → see timeline

Tasks:
- SwiftUI views: HomeView, FeedView, SleepView, DiaperView, TimelineView
- UniFFFI integration: import BabyCore via Swift bindings
- BabyCore instance created with SQLite path
- Call uniffi_api functions: add_baby(), log_breast_feed(), etc.
- Parse JSON responses (feeding_summary_json, etc.)
- Display next breast side: "Start on Left"
- Show daily summary with alert banner if present

Sample Code Flow:
1. HomeView displays daily_summary_json()
2. User taps "Feed" → FeedView
3. Select "Breast", "Right", 600 seconds
4. Call core.log_breast_feed("baby-id", "Right", 600)
5. Core returns "Left" (recommended next side)
6. Display "Next: Left" in FeedView
7. Return to HomeView, timeline refreshed
```

---

### I-1.4: Android MVP (Kotlin)

**Feature**: One-screen Android app, same as iOS, via Kotlin/JNI

```
User Story: "As an Android parent, I can log baby data in one tap"

Acceptance Criteria:
✅ Same UI as iOS (feed, sleep, diaper tabs)
✅ Timeline view with latest events
✅ Alerts displayed
✅ All data local (SQLite via UniFFI JNI)
✅ Build via ./gradlew assembleDebug

Tasks:
- Kotlin classes: MainActivity, FeedFragment, SleepFragment, DiaperFragment
- UniFFI JNI bindings: BabyCore loaded via System.loadLibrary()
- Call same Rust functions as iOS (via JNI)
- Parse JSON responses same as iOS
- Display next breast side recommendation
- Implement tabs: Feed, Sleep, Diaper, Timeline, Alerts

Same flow as iOS, via Kotlin → JNI → Rust core
```

---

### I-1.5: Integration + Polish

**Feature**: Tests, security review, release

```
User Story: "As a project lead, I can release PI-1 MVP with confidence"

Acceptance Criteria:
✅ cargo test --workspace passes
✅ cargo clippy --workspace passes
✅ iOS XCode build successful
✅ Android gradle build successful
✅ E2E smoke test: register baby, log 3 events, check daily summary
✅ Security review: crypto, FFI, rate limiting
✅ Adversarial test: bad UUIDs, invalid dates, empty feeds
✅ Beta release to TestFlight + Google Play

Tasks:
- Add integration tests
- Run clippy lint
- Fix clippy warnings
- Review uniffi bindings
- iOS App Store submission prep
- Android Play Store submission prep
```

---

## PROGRAM INCREMENT 2 (PI-2): Growth + Wellness + Web

**Timeframe**: Weeks 7-12
**Hypothesis**: Adding parental wellness + growth tracking increases retention 40%

### I-2.1: Growth Engine (WHO Curves)

```
User Story: "As a parent, I can log baby growth and see percentiles"

Functions to Implement:
- log_growth(baby_id, year, month, day, weight, height, head_cm) → entry_id
- list_growth_json(baby_id) → JSON array of GrowthEntry
- compute_percentiles(entries) → [weight_percentile, height_percentile, head_percentile]

Engine Logic:
- Query all growth entries for baby
- Map measurements to WHO/CDC reference curves
- Calculate percentile rank
- Alert if crossing percentile bands (red flag)
```

---

### I-2.2: Wellness Engine (EPDS)

```
User Story: "As a parent, I can track my mood and sleep, and get PPD screening"

Functions to Implement:
- log_wellness(caregiver_id, mood, hydration, meals, sleep_hours) → entry_id
- calculate_epds(entries) → EPDS score
- check_ppd_alert(caregiver_id) → Option<Alert>

EPDS Scoring (Edinburgh Postnatal Depression Screen):
- 10 questions, 0-3 points each
- Score ≥13: risk of depression
- Alert: "Consider talking to your doctor"
```

---

### I-2.3: Multi-Caregiver Sync (Local P2P)

```
User Story: "As co-parents, we can share baby data over WiFi without internet"

Functions to Implement:
- generate_pairing_code() → 6-digit code
- sync_to_peer(peer_address, local_db) → success
- receive_sync(peer_db) → merge

Technical:
- Bluetooth Low Energy (iOS) or WiFi Direct (Android)
- Simple CRDT-style merge (latest timestamp wins)
```

---

### I-2.4: SvelteKit PWA (WASM)

```
User Story: "As a parent on a browser, I can use the app offline on my computer"

Functions to Implement:
- Compile core with --features wasm
- Use wasm-pack to generate JavaScript bindings
- SvelteKit components call Wasm functions
- localStorage for persistent data

Technical:
- core/lib.rs with #[cfg(feature = "wasm")]
- core/wasm.rs: WebAssembly entry point
- SvelteKit /src/routes/
- Service Worker for offline support
```

---

### I-2.5: Reports + Export

```
User Story: "As a parent, I can export my data as PDF to share with pediatrician"

Functions to Implement:
- export_json(baby_id) → String (full backup)
- export_csv(baby_id) → String (feeds, sleeps, diapers)
- export_pdf(baby_id) → Vec<u8> (report with graphs)

Report Contents:
- Baby info (name, age, birth date)
- Summary (average feeds/day, sleep/day, diaper pattern)
- Growth chart (if measurements exist)
- Milestone checklist
- Parent summary (wellness scores)
```

---

---

## PROGRAM INCREMENT 3 (PI-3): Intelligence + Scale

**Timeframe**: Weeks 13-18
**Hypothesis**: AI insights + multi-language adoption increase DAU 3x

### I-3.1: Pattern Detection (Local ML)

```
User Story: "As a parent, I can see sleep and feeding patterns"

Functions to Implement:
- detect_sleep_pattern(baby_id) → Pattern { type: "3-4-hour-cycle", confidence: 0.85 }
- predict_next_feed(baby_id) → DateTime (when baby likely wants to feed)
- analyze_growth_velocity(baby_id) → "normal" | "accelerating" | "decelerating"

Technical:
- Simple statistical analysis (no heavy ML)
- Running average of intervals
- Anomaly detection via Z-score
```

---

### I-3.2: Internationalization (i18n)

```
User Story: "As a parent in France/Arabic country, I can use the app in my language"

Functions to Implement:
- translate(key: String, lang: "fr" | "en" | "ar") → String
- format_date(date, locale) → String (localized format)
- format_volume(ml, locale) → String ("120 ml" vs "120mL" vs "خخخ")

Languages:
- French (fr) — "Allaitement" not "Feeding"
- English (en) — existing
- Arabic (ar) — RTL layout
```

---

### I-3.3: Custom Activities + Tummy Time

```
User Story: "As a parent, I can log tummy time and track WHO recommendations (30min/day)"

Functions to Implement:
- add_activity(baby_id, activity_name: String, duration_secs: u32)
- list_activities(baby_id, hours: u32) → Vec<Activity>
- alert_tummy_time(baby_id) → Option<Alert> (if <30min today)

Activities:
- Tummy time (WHO 30min/day)
- Bath time
- Skin-to-skin
- Custom

Alerts:
- "Tummy time: 5min today (goal: 30min)"
```

---

### I-3.4: Apple Watch + Widgets

```
User Story: "As an iOS parent, I can quick-log from Apple Watch"

Implementation:
- watchOS app in Swift
- WidgetKit: Show next feed time, last diaper, total sleep
- Complications: Quick-add feed/diaper button
- Handoff: Start on watch, finish on iPhone

Functions:
- Same uniffi_api as iPhone
- Pass device data to watch via CloudKit sync
```

---

### I-3.5: Cloud Sync (E2E Encrypted)

```
User Story: "As a multi-device parent, I can sync my data to cloud (encrypted)"

Backend Ready:
- gRPC service (RegisterDevice, Push, Pull, Health)
- JWT auth (90-day expiry)
- Rate limiting
- PostgreSQL storage

Client:
- Encrypt local DB with AES-256-GCM
- Push ciphertext via Push RPC
- Pull encrypted blobs via Pull RPC
- Decrypt locally (zero-knowledge)

Acceptance:
- Server never sees plaintext
- User owns encryption key
- Optional (opt-in only)
```

---

---

## FEATURE → FUNCTION CROSS-REFERENCE

### Daily Logging

| Action | Story | Function | Implementation |
|--------|-------|----------|-----------------|
| Add baby | US-001 | `add_baby(name, birth_year, month, day)` | Baby::new(), db.insert_baby() |
| Log breast feed | US-101 | `log_breast_feed(baby_id, side, duration)` | FeedingEngine::log_breast() |
| Log bottle feed | US-101 | `log_bottle_feed(baby_id, content, volume)` | FeedingEngine::log_bottle() |
| Log solid food | US-101 | `log_solid(baby_id, food_name, is_new, allergen)` | Feed::new() + insert |
| Get next breast side | US-101 | `last_breast_side(baby_id)` | FeedingEngine::last_side() |
| Start sleep | US-102 | `start_sleep(baby_id, sleep_type)` | SleepEngine::start() |
| End sleep | US-102 | `end_sleep(sleep_id)` | SleepEngine::end() |
| Log diaper | US-103 | `log_diaper(baby_id, type, has_rash)` | DiaperEngine::log() |
| Log growth | US-104 | `log_growth(baby_id, date, weight, height, head)` | GrowthEntry::new() + insert |
| Add milestone | US-105 | `add_milestone(baby_id, domain, description, age_months)` | Milestone::new() + insert |
| Toggle milestone | US-105 | `toggle_milestone(milestone_id)` | db.toggle_milestone() |

### Analytics & Alerts

| Action | Story | Function | Implementation |
|--------|-------|----------|-----------------|
| Get feeding summary | US-201 | `feeding_summary_json(baby_id)` | FeedingEngine::daily_summary() |
| Get sleep summary | US-201 | `sleep_summary_json(baby_id)` | SleepEngine::daily_summary() |
| Get diaper summary | US-201 | `diaper_summary_json(baby_id)` | DiaperEngine::daily_summary() |
| Get daily overview | US-201 | `daily_summary_json(baby_id)` | Combines all summaries + alerts |
| Check alerts | US-202 | `check_alerts_json(baby_id)` | AlertEngine::check_all() |
| Get growth percentiles | US-301 (PI-2) | `compute_percentiles(baby_id)` | NEW in PI-2 |
| Calculate EPDS | US-302 (PI-2) | `calculate_epds(caregiver_id)` | NEW in PI-2 |

### Sync & Export

| Action | Story | Function | Implementation |
|--------|-------|----------|-----------------|
| Register device | US-401 (PI-2) | `register_device(pairing_code, device_id)` | Backend gRPC RPC |
| Push data | US-401 (PI-2) | `push(ciphertext, nonce, key_hash)` | Backend gRPC RPC + JWT |
| Pull data | US-401 (PI-2) | `pull(since_timestamp)` | Backend gRPC RPC + JWT |
| Encrypt data | US-402 (PI-2) | `encrypt(key, plaintext)` | crypto/encryption.rs |
| Decrypt data | US-402 (PI-2) | `decrypt(key, ciphertext)` | crypto/encryption.rs |
| Export JSON | US-501 (PI-2) | `export_json(baby_id)` | NEW export module |
| Export PDF | US-501 (PI-2) | `export_pdf(baby_id)` | NEW export module |

---

---

## COMPLETION CHECKLIST

### PI-1 (MVP)
- [x] Models: Baby, Feed, Sleep, Diaper, Growth, Milestone
- [x] Engines: Feeding, Sleep, Diaper, Alerts
- [x] Storage: SQLite schema + CRUD
- [x] Crypto: AES-256-GCM + Argon2id
- [x] UniFFI API: 25+ exported functions
- [x] Backend: gRPC sync service (ready, not deployed in PI-1)
- [x] iOS: SwiftUI MVP (planned, not started)
- [x] Android: Kotlin MVP (planned, not started)
- [x] Tests: 15+ unit tests
- [ ] Release: TestFlight + Play Store (PI-1.5)

### PI-2 (Growth + Wellness + Web)
- [ ] Growth engine + WHO curves
- [ ] Wellness engine + EPDS scoring
- [ ] Multi-caregiver sync (P2P)
- [ ] SvelteKit PWA + WASM
- [ ] Export (JSON, CSV, PDF)

### PI-3 (Intelligence + Scale)
- [ ] Pattern detection
- [ ] i18n (fr, en, ar)
- [ ] Custom activities
- [ ] Apple Watch
- [ ] Cloud sync (backend deployed)

---

**Generated**: March 2025
**Repository**: https://github.com/macaron-software/baby
