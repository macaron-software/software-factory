# Test Ideation - Fervenza IoT Platform

## Team: Pierre (Architecture), Chloé (UX), Nadia (Security), Alexandre (PM)

---

## 1. UNIT TESTS - Rust Crates

### Authentication Module (`crates/auth/`)

```rust
// tests/auth_tests.rs
#[test]
fn test_valid_credentials_authenticate() {
    // Arrange
    let creds = Credentials::new("user@example.com", "correct_password");

    // Act
    let result = authenticate(&creds);

    // Assert
    assert!(result.is_ok());
}

#[test]
fn test_invalid_password_rejected() {
    // Arrange
    let creds = Credentials::new("user@example.com", "wrong_password");

    // Act
    let result = authenticate(&creds);

    // Assert
    assert!(result.is_err());
    assert_eq!(result.unwrap_err(), AuthError::InvalidCredentials);
}

#[test]
fn test_session_expiration_handled() {
    // Arrange
    let session = Session::new_expired();

    // Act
    let result = validate_session(&session);

    // Assert
    assert!(result.is_err());
}
```

### Data Validation (`crates/validation/`)

```rust
#[test]
fn test_email_validation_accepts_valid() {
    assert!(validate_email("user@fervenza.io").is_ok());
}

#[test]
fn test_email_validation_rejects_invalid() {
    assert!(validate_email("not-an-email").is_err());
}

#[test]
fn test_required_fields_all_present() {
    let input = json!({
        "name": "Device 1",
        "type": "sensor",
        "status": "active"
    });
    assert!(validate_required(&input, &["name", "type", "status"]).is_ok());
}
```

---

## 2. INTEGRATION TESTS - API Endpoints

### Backend API (`backend/src/api/`)

```python
# backend/tests/test_api.py
import pytest

class TestAuthEndpoints:
    def test_login_returns_jwt_on_success(self, client):
        response = client.post("/api/auth/login", json={
            "email": "user@fervenza.io",
            "password": "valid_password"
        })
        assert response.status_code == 200
        assert "token" in response.json()

    def test_login_returns_401_on_failure(self, client):
        response = client.post("/api/auth/login", json={
            "email": "user@fervenza.io",
            "password": "wrong_password"
        })
        assert response.status_code == 401

class TestDeviceEndpoints:
    def test_list_devices_returns_paginated(self, client, auth_token):
        response = client.get("/api/devices?page=1&limit=10",
            headers={"Authorization": f"Bearer {auth_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_filter_devices_by_status(self, client, auth_token):
        response = client.get("/api/devices?status=active",
            headers={"Authorization": f"Bearer {auth_token}"})
        assert all(d["status"] == "active" for d in response.json()["items"])
```

---

## 3. SECURITY TESTS (Nadia)

### Security Test Suite (`tests/security/`)

```python
# tests/security/test_sql_injection.py
class TestSQLInjectionPrevention:
    def test_login_field_sql_injection(self, client):
        payload = {"email": "' OR '1'='1", "password": "anything"}
        response = client.post("/api/auth/login", json=payload)
        # Should not expose SQL errors
        assert response.status_code in [400, 401]
        assert "sql" not in response.text.lower()

    def test_device_name_sql_injection(self, client, auth_token):
        payload = {"name": "'; DROP TABLE devices; --"}
        response = client.post("/api/devices", json=payload,
            headers={"Authorization": f"Bearer {auth_token}"})
        assert response.status_code in [400, 422]

# tests/security/test_xss.py
class TestXSSPrevention:
    def test_device_description_xss(self, client, auth_token):
        payload = {"description": "<script>alert('xss')</script>"}
        response = client.post("/api/devices", json=payload,
            headers={"Authorization": f"Bearer {auth_token}"})
        # Should be sanitized or rejected
        assert response.status_code in [400, 422]

# tests/security/test_password_hashing.py
class TestPasswordSecurity:
    def test_passwords_hashed_with_bcrypt(self, db):
        user = get_user_by_email("user@fervenza.io")
        assert user.password_hash.startswith("$2")  # bcrypt prefix
        assert user.password_hash != "plain_password"
```

---

## 4. UX TESTS (Chloé)

### Performance Tests (`tests/performance/`)

```python
# tests/performance/test_load_times.py
class TestPageLoadPerformance:
    @pytest.mark.slow
    def test_homepage_loads_under_3_seconds(self, browser):
        page = browser.new_page()
        start = time.time()
        page.goto("https://fervenza.io")
        load_time = time.time() - start
        assert load_time < 3.0, f"Page took {load_time}s to load"

    def test_api_response_under_500ms(self, client):
        start = time.time()
        response = client.get("/api/devices")
        elapsed = time.time() - start
        assert elapsed < 0.5

# tests/accessibility/
class TestAccessibility:
    def test_keyboard_navigation_works(self, browser):
        page = browser.new_page()
        page.goto("/dashboard")
        page.keyboard.press("Tab")
        # Should focus first interactive element
        assert page.evaluate("document.activeElement.tabIndex") >= 0

    def test_aria_labels_present(self, browser):
        page = browser.new_page()
        page.goto("/dashboard")
        # Check buttons have aria-labels
        buttons = page.query_selector_all("button")
        for btn in buttons:
            label = btn.get_attribute("aria-label")
            assert label is not None, "Button missing aria-label"

# tests/responsive/
class TestMobileResponsiveness:
    def test_mobile_viewport_renders(self, browser):
        page = browser.new_page(viewport={"width": 375, "height": 667})
        page.goto("/dashboard")
        assert page.is_visible(".mobile-menu")
```

---

## 5. E2E TESTS - User Journeys

### Playwright Test Suite (`tests/e2e/`)

```typescript
// tests/e2e/user-journeys.spec.ts
import { test, expect } from "@playwright/test";

test.describe("User Registration Flow", () => {
  test("complete registration journey", async ({ page }) => {
    // 1. Navigate to registration
    await page.goto("/register");

    // 2. Fill form
    await page.fill('[name="email"]', "newuser@fervenza.io");
    await page.fill('[name="password"]', "SecureP@ss123");
    await page.fill('[name="confirm"]', "SecureP@ss123");
    await page.click('button[type="submit"]');

    // 3. Verify email sent
    await expect(page.locator(".success-message")).toContainText("Check your email");
  });
});

test.describe("Device Management Flow", () => {
  test("add new device end-to-end", async ({ page, authenticated }) => {
    await page.goto("/devices");
    await page.click(".add-device-btn");
    await page.fill('[name="name"]', "Living Room Sensor");
    await page.selectOption('[name="type"]', "temperature");
    await page.click('button:has-text("Save")');

    // Verify device appears in list
    await expect(page.locator(".device-list")).toContainText("Living Room Sensor");
  });
});

test.describe("Password Reset Flow", () => {
  test("complete password reset", async ({ page }) => {
    await page.goto("/login");
    await page.click("text=Forgot password?");
    await page.fill('[name="email"]', "user@fervenza.io");
    await page.click('button:has-text("Send reset link")');

    // Should show confirmation
    await expect(page.locator(".success-message")).toBeVisible();
  });
});
```

---

## 6. FIRMWARE TESTS

### Embedded Tests (`firmware/tests/`)

```c
// firmware/test/test_sensors.c
void test_temperature_sensor_reading(void) {
    float temp = read_temperature();
    // Sensor should read reasonable range
    TEST_ASSERT_TRUE(temp > -40.0f && temp < 85.0f);
}

void test_sensor_calibration(void) {
    calibrate_sensor(25.0f);  // 25°C reference
    float reading = read_temperature();
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 25.0f, reading);
}

// firmware/test/test_memory.c
void test_memory_allocation_no_leak(void) {
    size_t before = get_free_heap();
    void *ptr = custom_alloc(100);
    TEST_ASSERT_NOT_NULL(ptr);
    custom_free(ptr);
    size_t after = get_free_heap();
    TEST_ASSERT_EQUAL(before, after);
}
```

---

## Test Priority Matrix

| Test Category      | Priority | Owner     | Sprint |
| ------------------ | -------- | --------- | ------ |
| Security (SQL/XSS) | P0       | Nadia     | 1      |
| Auth Unit Tests    | P0       | Pierre    | 1      |
| API Integration    | P1       | Pierre    | 2      |
| E2E Journeys       | P1       | Alexandre | 2      |
| UX Performance     | P2       | Chloé     | 3      |
| Firmware Tests     | P2       | Pierre    | 3      |
| Accessibility      | P2       | Chloé     | 3      |

---

## Coverage Targets

- **Unit Tests**: 80% code coverage on `crates/auth`, `crates/validation`
- **API Tests**: 100% endpoint coverage
- **Security**: OWASP Top 10 coverage
- **E2E**: Top 5 user journeys
- **Performance**: Core pages < 3s load time
