# NARABAYBY QUICK REFERENCE

## PROJECT OVERVIEW
- **Name**: NARABAYBY (Evidence-based baby & parent tracker)
- **Language**: Rust (core) + Swift/Kotlin/JavaScript (clients)
- **Repository**: https://github.com/macaron-software/baby
- **License**: AGPL-3.0-or-later

## CODEBASE STATISTICS
| Metric | Value |
|--------|-------|
| Core Library (Rust) | 2,006 lines |
| Backend (Rust) | 632 lines |
| Public APIs | 205+ items |
| Data Models | 8 types |
| Engines | 4 (Feeding, Sleep, Diaper, Alerts) |
| Database Tables | 8 tables |
| gRPC RPCs | 4 endpoints |

---

## DATA MODELS (core/src/models/)

### 1. **Baby**
- `id: Uuid` — Unique identifier
- `name: String` — Baby's name
- `birth_date: NaiveDate` — Birth date
- `sex: Option<Sex>` — Male/Female
- Methods: `age_days()`, `age_months()`

### 2. **Feed**
- **Types**: Breast (side, duration), Bottle (content, volume), Solid (name, allergen), Pumping
- `caregiver_id: Option<Uuid>` — Who logged it
- Supports multi-type feeding tracking

### 3. **Sleep**
- **Types**: Nap, Night
- `started_at, ended_at` — Duration tracking
- `is_active()` — Still sleeping?

### 4. **Diaper**
- **Types**: Wet, Dirty, Mixed, Dry
- `has_rash: bool` — Rash flag
- `is_wet()` — Hydration check

### 5. **Growth**
- `weight_kg, height_cm, head_cm` — Optional measurements
- `measured_on` ≠ `created_at` — Supports backdated entries

### 6. **Milestone**
- **Domains**: Social, Language, Cognitive, Motor (CDC 2022)
- `expected_age_months: u8` — Expected age
- `achieved_on: Option<NaiveDate>` — Achievement tracking

### 7. **Wellness** (Parental)
- `mood, hydration_ml, meals_count, sleep_hours`
- Foundation for PPD detection (PI-2)

### 8. **Caregiver**
- **Roles**: Parent, Grandparent, Nanny, Other
- Multi-caregiver support

---

## ENGINES (core/src/engines/)

### FeedingEngine
```rust
log_breast(db, baby_id, side, duration) → next_side
log_bottle(db, baby_id, content, amount)
daily_summary(db, baby_id) → FeedingSummary
  ├─ breast_count, breast_total_secs
  ├─ bottle_count, bottle_total_ml
  ├─ solid_count, pumping_count
```

**Key Feature**: Alternating breast side recommendation

---

### SleepEngine
```rust
start(db, baby_id, sleep_type) → Sleep
end(db, sleep_id)
daily_summary(db, baby_id) → SleepSummary
  ├─ total_sleep_secs
  ├─ nap_count, nap_sleep_secs, night_sleep_secs
wake_time_secs(db, baby_id) → Option<u32>  // For alerts
```

**Key Feature**: Separate nap vs night tracking

---

### DiaperEngine
```rust
log(db, baby_id, type, has_rash)
daily_summary(db, baby_id) → DiaperSummary
check_threshold(db, baby) → Option<DiaperAlert>  // AAP standards
```

**AAP Thresholds** (wet diapers):
- Day 1: ≥1
- Day 2: ≥2
- Day 3-5: ≥3
- Week 1+: ≥6/24h

---

### AlertEngine
```rust
check_all(db, baby) → Vec<Alert>
```

**Alerts Checked**:
1. **Diaper low** — Below AAP threshold (Urgent if 0, Warning if low)
2. **No feeds** — No feeding in 24h (Warning)
3. **Wake window** — >2h for <3mo, >3h for older (Info)

All alerts include source_url for medical credibility.

---

## CRYPTO (core/src/crypto/encryption.rs)

### Key Derivation
```rust
derive_key(passphrase, salt?) → (key: [u8; 32], salt: [u8; 16])
```
- **Algorithm**: Argon2id (memory-hard)
- **Output**: 256-bit key
- **Purpose**: Optional for V1, required for cloud sync

### Encryption
```rust
encrypt(key, plaintext) → Vec<u8>  // [nonce(12)] || [ciphertext] || [tag]
decrypt(key, data) → Vec<u8>
```
- **Algorithm**: AES-256-GCM
- **Nonce**: 12-byte random per encryption
- **Zero AAD**: Plain authenticated encryption

### Memory Safety
```rust
zeroize_key(key)  // Securely clear from memory
```

---

## STORAGE (core/src/storage/)

### Database Tables
```sql
babies (id, name, birth_date, created_at)
caregivers (id, name, role, created_at)
feeds (id, baby_id, caregiver_id, feed_type, feed_data, started_at, ended_at, ...)
sleeps (id, baby_id, caregiver_id, sleep_type, started_at, ended_at, ...)
diapers (id, baby_id, caregiver_id, diaper_type, has_rash, logged_at, ...)
growth_entries (id, baby_id, measured_on, weight_kg, height_cm, head_cm, ...)
milestones (id, baby_id, domain, description, expected_age_months, achieved_on, ...)
wellness_entries (id, caregiver_id, mood, hydration_ml, meals_count, sleep_hours, ...)
```

**Indexes**: baby_id + timestamp on hot tables

**Platform**:
- **Native** (iOS/Android): SQLite embedded
- **WASM** (Web): localStorage

---

## UniFFI API (core/src/uniffi_api.rs)

### Constructor
```swift
let core = BabyCore(db_path: "db.sqlite")  // iOS
let core = BabyCore.new(dbPath)            // Android
```

### Key Methods
```swift
// Baby
add_baby(name, year, month, day) → baby_id
list_babies_json() → String (JSON)

// Feeding
log_breast_feed(baby_id, side, duration_secs) → next_side
log_bottle_feed(baby_id, content, amount_ml)
feeding_summary_json(baby_id) → String

// Sleep
start_sleep(baby_id, sleep_type) → sleep_id
end_sleep(sleep_id)
sleep_summary_json(baby_id) → String

// Diaper
log_diaper(baby_id, type, has_rash)
diaper_summary_json(baby_id) → String

// Growth
log_growth(baby_id, year, month, day, weight, height, head_cm) → entry_id
list_growth_json(baby_id) → String

// Milestones
add_milestone(baby_id, domain, description, expected_months) → milestone_id
toggle_milestone(milestone_id)
list_milestones_json(baby_id) → String

// Alerts
check_alerts_json(baby_id) → String  // [Alert, Alert, ...]

// Combined
daily_summary_json(baby_id) → String  // { feeds: {...}, sleep: {...}, diapers: {...}, alerts: [...] }
```

---

## BACKEND (backend/src/main.rs)

### Architecture: Zero-Knowledge Sync

```
[iOS/Android/Web]
    ↓ (AES-256-GCM encrypted)
[NaraBayby Backend]
    ↓ (stores ciphertext only)
[PostgreSQL]
```

**Principle**: Server never sees plaintext.

---

### gRPC Service

#### 1. RegisterDevice (Public, Rate-Limited)
```protobuf
Request:  { pairing_code: String, device_id: UUID }
Response: { device_id: UUID, token: JWT, status: "registered" }
```
- **Rate Limit**: 5 registrations per IP per minute
- **JWT Expiry**: 90 days
- **Validation**: pairing_code ≥6 chars, device_id must be UUID

---

#### 2. Push (Authenticated, Rate-Limited)
```protobuf
Request:  { ciphertext: bytes, nonce: bytes, key_hash: String }
Response: { id: UUID, status: "ok" }
```
- **Auth**: JWT required
- **Rate Limit**: 60 per device per minute
- **Storage**: PostgreSQL sync_records table
- **Server sees**: Only encrypted blobs (not plaintext)

---

#### 3. Pull (Authenticated, Rate-Limited)
```protobuf
Request:  { since: ISO8601 timestamp }
Response: { records: [SyncRecord, ...] }
  SyncRecord: { id, device_id, ciphertext, nonce, key_hash, created_at }
```
- **Auth**: JWT required
- **Rate Limit**: 120 per device per minute
- **Query**: Records WHERE device_id = $1 AND created_at > $2
- **Updates**: Sets last_sync timestamp

---

#### 4. Health (Public)
```protobuf
Response: { status: "ok", version: "x.y.z", zero_knowledge: true }
```

---

### Security Features

| Feature | Implementation |
|---------|-----------------|
| **JWT Auth** | HMAC-SHA256, 90-day expiry |
| **Rate Limiting** | Per IP (register), per device_id (push/pull) |
| **CORS** | Whitelist: baby.macaron-software.com, localhost:5173 |
| **gRPC-Web** | Browser support with strict CORS |
| **Pool** | PostgreSQL 16 max connections |
| **Error Types** | UNAUTHENTICATED, RESOURCE_EXHAUSTED, INVALID_ARGUMENT, INTERNAL |

---

## FEATURES IMPLEMENTED (PI-1)

| Feature | Status | Component |
|---------|--------|-----------|
| Log baby feeds (breast, bottle, solids, pumping) | ✅ | FeedingEngine |
| Log sleep (naps, nights) | ✅ | SleepEngine |
| Log diapers (wet, dirty, mixed) with rash | ✅ | DiaperEngine |
| Log growth (weight, height, head) | ✅ | GrowthEntry |
| Track milestones (CDC 2022, 4 domains) | ✅ | Milestone |
| AAP-based diaper alerts | ✅ | AlertEngine |
| Wake window alerts | ✅ | AlertEngine |
| No-feed-in-24h alerts | ✅ | AlertEngine |
| Multi-caregiver support | ✅ | Caregiver model |
| Alternating breast side prompt | ✅ | FeedingEngine |
| Daily summary (combined view) | ✅ | daily_summary_json |
| AES-256-GCM encryption | ✅ | crypto/encryption.rs |
| Zero-knowledge sync backend | ✅ | backend/main.rs |

---

## PLANNED FEATURES (PI-2 & PI-3)

| Feature | PI | Component |
|---------|----|-----------| 
| Growth percentiles (WHO curves) | PI-2 | New engine |
| Parental wellness tracking | PI-2 | WellnessEngine |
| EPDS screening (validated) | PI-2 | New EPDS engine |
| PPD detection alerts | PI-2 | AlertEngine update |
| Multi-device sync | PI-2 | Backend activation |
| SvelteKit PWA (WASM) | PI-2 | wasm feature |
| Export (PDF/CSV/JSON) | PI-2 | New export module |
| Pattern detection (local ML) | PI-3 | New patterns engine |
| Internationalization (i18n) | PI-3 | i18n module |
| Apple Watch support | PI-3 | SwiftUI update |
| Custom activities & tummy time | PI-3 | New models |

---

## DEPENDENCIES

### Core
```toml
[features]
native = ["rusqlite", "aes-gcm", "argon2", "uniffi"]  # iOS/Android
wasm = ["wasm-bindgen", "web-sys", "js-sys"]         # Web

# All
serde, serde_json, chrono, uuid, thiserror, rand
# Native only
rusqlite, aes-gcm, argon2, zeroize, uniffi
# WASM only
wasm-bindgen, web-sys, js-sys
```

### Backend
```toml
tonic, tokio, tower-http, jsonwebtoken, http
serde, chrono, uuid, deadpool-postgres, tokio-postgres
tonic-web, tracing, prost
```

---

## SAFe STRATEGIC THEMES

| ID | Theme | Status | KPI |
|----|-----------|---------|----|
| ST-1 | Evidence-based tracking | ✅ DONE | 100% thresholds peer-reviewed |
| ST-2 | Privacy-by-design | ✅ DONE | Zero plaintext on server |
| ST-3 | Multi-platform core | ✅ DONE | 1 Rust crate, 3 frontends |
| ST-4 | Parental wellness | 🔄 PLANNED (PI-2) | PPD detection |
| ST-5 | Continuous quality | 🔄 PLANNED (CONTINUOUS) | Adversarial testing |

---

## DEVELOPER SETUP

```bash
cd /tmp/baby
cargo build --workspace
cargo test --workspace
cargo clippy --workspace

# Native (iOS)
cd core
cargo build --target aarch64-apple-ios --features native

# WASM (Web)
cd core
wasm-pack build --target web --features wasm
```

---

## DOCUMENTATION
- **Full Exploration**: `baby_exploration.md` (1,794 lines)
- **Architecture**: CLAUDE.md, DESIGN_SYSTEM.md, RESEARCH.md, SAFE.md
- **Tests**: Unit tests in `core/src/` and `backend/src/`

---

**Generated**: March 2025
**Repository**: https://github.com/macaron-software/baby
