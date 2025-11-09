# MUTT v2.3 Test Suite Documentation

Comprehensive unit test suite for all MUTT services with 100+ test cases.

---

## Test Coverage

### Test Files

| File | Service | Test Count | Coverage |
|------|---------|------------|----------|
| `test_ingestor_unit.py` | Ingestor | 30+ tests | API key auth, JSON validation, backpressure, Vault |
| `test_alerter_unit.py` | Alerter | 40+ tests | Rule matching, priority selection, janitor, BRPOPLPUSH |
| `test_moog_forwarder_unit.py` | Moog Forwarder | 35+ tests | Rate limiting, retry logic, DLQ, exponential backoff |
| `test_webui_unit.py` | Web UI | 30+ tests | CRUD operations, caching, authentication |
| `conftest.py` | Fixtures | - | Shared mocks and test data |

**Total:** 135+ unit tests

---

## Quick Start

### 1. Install Dependencies

```bash
# Navigate to project root
cd /path/to/MUTT_v2

# Install test dependencies
pip install -r tests/requirements-test.txt
```

### 2. Run All Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html --cov-report=term

# Run in parallel (faster)
pytest tests/ -n auto
```

### 3. View Results

```bash
# View coverage report
open htmlcov/index.html

# Or on Windows
start htmlcov/index.html
```

---

## Running Specific Tests

### By Service

```bash
# Test Ingestor only
pytest tests/test_ingestor_unit.py -v

# Test Alerter only
pytest tests/test_alerter_unit.py -v

# Test Moog Forwarder only
pytest tests/test_moog_forwarder_unit.py -v

# Test Web UI only
pytest tests/test_webui_unit.py -v
```

### By Test Class

```bash
# Test API key authentication
pytest tests/test_ingestor_unit.py::TestAPIKeyAuthentication -v

# Test rule matching
pytest tests/test_alerter_unit.py::TestRuleMatchingContains -v

# Test rate limiting
pytest tests/test_moog_forwarder_unit.py::TestRateLimiting -v
```

### By Individual Test

```bash
# Run single test
pytest tests/test_ingestor_unit.py::TestAPIKeyAuthentication::test_valid_api_key_accepted -v
```

---

## Test Organization

### Test Markers

Tests are organized with pytest markers:

```python
@pytest.mark.unit          # Unit tests (all tests default to this)
@pytest.mark.integration   # Integration tests (require real services)
@pytest.mark.slow          # Slow tests (>1 second)
```

**Run by marker:**

```bash
# Run only unit tests
pytest tests/ -m unit -v

# Run only integration tests (requires services)
pytest tests/ -m integration -v

# Skip slow tests
pytest tests/ -m "not slow" -v
```

---

## Test Coverage Details

### Ingestor Service Tests

**`test_ingestor_unit.py`** - 30+ tests

#### TestAPIKeyAuthentication (5 tests)
- ✅ Valid API key accepted
- ✅ Invalid API key rejected
- ✅ Empty API key rejected
- ✅ None API key rejected
- ✅ Timing attack resistance (constant-time comparison)

#### TestJSONValidation (5 tests)
- ✅ Valid JSON accepted
- ✅ Malformed JSON rejected
- ✅ Empty payload rejected
- ✅ Null payload handled
- ✅ Empty object accepted

#### TestBackpressureHandling (4 tests)
- ✅ Queue under capacity accepts messages
- ✅ Queue at capacity rejects (503)
- ✅ Queue over capacity rejects
- ✅ Queue at 99% still accepts

#### TestRedisOperations (5 tests)
- ✅ Message pushed to queue
- ✅ Metrics incremented atomically
- ✅ Redis connection failure handled
- ✅ Pipeline atomic execution
- ✅ All operations in transaction

#### TestVaultIntegration (4 tests)
- ✅ Vault authentication success
- ✅ Secrets fetched correctly
- ✅ Token renewal logic
- ✅ Authentication failure handled

#### TestMessageFlow (4 tests)
- ✅ Complete successful flow
- ✅ Flow fails on invalid API key
- ✅ Flow fails on invalid JSON
- ✅ Flow fails on queue full

---

### Alerter Service Tests

**`test_alerter_unit.py`** - 40+ tests

#### TestRuleMatchingContains (4 tests)
- ✅ Contains match found
- ✅ Contains match not found
- ✅ Case sensitivity enforced
- ✅ Partial word matching

#### TestRuleMatchingRegex (4 tests)
- ✅ Regex pattern matches
- ✅ Alternative patterns work
- ✅ No match handled
- ✅ Invalid regex raises error

#### TestRuleMatchingOIDPrefix (4 tests)
- ✅ Exact OID match
- ✅ Prefix match (child OID)
- ✅ Different OID no match
- ✅ Parent OID no match

#### TestPrioritySelection (3 tests)
- ✅ Lowest priority wins
- ✅ Single match selected
- ✅ No match returns None

#### TestEnvironmentDetection (4 tests)
- ✅ Dev host detected
- ✅ Prod host detected
- ✅ Correct handling for dev
- ✅ Correct handling for prod

#### TestUnhandledEventDetection (4 tests)
- ✅ Counter increments
- ✅ Threshold detection
- ✅ Lua script prevents duplicates
- ✅ Duplicate trigger prevention

#### TestJanitorLogic (5 tests)
- ✅ Orphaned lists detected
- ✅ Heartbeat check
- ✅ Dead pod detection
- ✅ Orphan recovery
- ✅ Heartbeat maintenance

#### TestBRPOPLPUSHPattern (3 tests)
- ✅ Message moved atomically
- ✅ Message deleted on success
- ✅ Message remains on failure

#### TestDatabaseOperations (4 tests)
- ✅ Audit log insert
- ✅ Partition not found error
- ✅ Connection pool getconn
- ✅ Connection pool putconn

#### TestSCANvsKEYS (2 tests)
- ✅ SCAN used (not KEYS)
- ✅ SCAN iteration works

---

### Moog Forwarder Tests

**`test_moog_forwarder_unit.py`** - 35+ tests

#### TestRateLimiting (6 tests)
- ✅ Allows under limit
- ✅ Blocks at limit
- ✅ Blocks over limit
- ✅ Lua script execution
- ✅ Lua script blocks
- ✅ Sliding window cleanup

#### TestRetryLogic (4 tests)
- ✅ Exponential backoff calculation
- ✅ Max delay enforced
- ✅ Retry count increments
- ✅ Max retries check

#### TestSmartRetryDecisions (5 tests)
- ✅ 2xx success, no retry
- ✅ 4xx client error, no retry (DLQ)
- ✅ 5xx server error, retry
- ✅ 408 timeout, retry
- ✅ 429 rate limit, retry

#### TestDeadLetterQueue (3 tests)
- ✅ Message to DLQ on 4xx
- ✅ Message to DLQ after max retries
- ✅ Message removed from processing

#### TestMoogWebhookCalls (5 tests)
- ✅ Successful webhook call
- ✅ Timeout handled
- ✅ Connection error handled
- ✅ 5xx error triggers retry
- ✅ 4xx error goes to DLQ

#### TestRateLimitCoordination (2 tests)
- ✅ Shared rate limit key
- ✅ Global limit enforced

---

### Web UI Tests

**`test_webui_unit.py`** - 30+ tests

#### TestAPIAuthentication (6 tests)
- ✅ Valid API key in header
- ✅ Valid API key in query param
- ✅ Invalid API key rejected
- ✅ Health endpoint no auth
- ✅ Metrics endpoint no auth
- ✅ Dashboard no auth

#### TestMetricsCaching (4 tests)
- ✅ Cache miss fetches from Redis
- ✅ Cache hit returns cached data
- ✅ Cache TTL configurable
- ✅ Cache refresh on expiry

#### TestAlertRulesCRUD (5 tests)
- ✅ List rules
- ✅ Create rule
- ✅ Update rule
- ✅ Delete rule
- ✅ Rule validation

#### TestAuditLogQueries (3 tests)
- ✅ Paginated listing
- ✅ Filtering by hostname
- ✅ Total count

#### TestDevHostsCRUD (4 tests)
- ✅ List dev hosts
- ✅ Add dev host
- ✅ Delete dev host
- ✅ Duplicate handled

#### TestDeviceTeamsCRUD (4 tests)
- ✅ List teams
- ✅ Add team
- ✅ Update team
- ✅ Delete team

---

## Coverage Goals

### Current Coverage Targets

| Service | Target Coverage | Current Status |
|---------|----------------|----------------|
| Ingestor | 80% | ⏰ Pending measurement |
| Alerter | 80% | ⏰ Pending measurement |
| Moog Forwarder | 80% | ⏰ Pending measurement |
| Web UI | 75% | ⏰ Pending measurement |

### Generate Coverage Report

```bash
# Run tests with coverage
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# View detailed report
open htmlcov/index.html

# Show coverage summary
pytest tests/ --cov=. --cov-report=term
```

---

## Test Execution Options

### Verbosity Levels

```bash
# Minimal output
pytest tests/

# Show test names
pytest tests/ -v

# Show test names + print statements
pytest tests/ -v -s

# Very verbose (show all details)
pytest tests/ -vv
```

### Output Formats

```bash
# Generate HTML report
pytest tests/ --html=report.html --self-contained-html

# Generate JSON report
pytest tests/ --json-report --json-report-file=report.json

# JUnit XML (for CI/CD)
pytest tests/ --junitxml=junit.xml
```

### Parallel Execution

```bash
# Auto-detect CPU count
pytest tests/ -n auto

# Use 4 workers
pytest tests/ -n 4

# Distribute by file (faster)
pytest tests/ -n auto --dist loadfile
```

### Failed Test Rerun

```bash
# Run only failed tests from last run
pytest tests/ --lf

# Run failed first, then all
pytest tests/ --ff
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: MUTT Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r tests/requirements-test.txt
      - name: Run tests
        run: pytest tests/ --cov=. --junitxml=junit.xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

### GitLab CI Example

```yaml
test:
  image: python:3.9
  script:
    - pip install -r requirements.txt
    - pip install -r tests/requirements-test.txt
    - pytest tests/ --cov=. --junitxml=junit.xml
  artifacts:
    reports:
      junit: junit.xml
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

```bash
# Problem: ModuleNotFoundError: No module named 'ingestor_service'
# Solution: Run pytest from project root
cd /path/to/MUTT_v2
pytest tests/ -v
```

#### 2. Fixture Not Found

```bash
# Problem: fixture 'mock_redis_client' not found
# Solution: Ensure conftest.py is in tests/ directory
ls tests/conftest.py
```

#### 3. Slow Tests

```bash
# Solution: Run in parallel
pytest tests/ -n auto

# Or skip slow tests
pytest tests/ -m "not slow"
```

#### 4. Coverage Not Working

```bash
# Problem: No coverage data collected
# Solution: Install pytest-cov
pip install pytest-cov

# Run with --cov flag
pytest tests/ --cov=.
```

---

## Best Practices

### Writing New Tests

1. **Use descriptive test names**
   ```python
   def test_api_key_authentication_rejects_invalid_key(self):
       """Test that invalid API key is rejected with 401"""
   ```

2. **Follow AAA pattern**
   ```python
   def test_example(self):
       # Arrange
       data = {"key": "value"}

       # Act
       result = process(data)

       # Assert
       assert result == expected
   ```

3. **Use fixtures for setup**
   ```python
   def test_with_fixture(self, mock_redis_client):
       mock_redis_client.ping.return_value = True
       assert mock_redis_client.ping()
   ```

4. **Test one thing per test**
   - Each test should verify one behavior
   - Multiple assertions OK if testing same behavior

5. **Mock external dependencies**
   - Don't call real Redis, PostgreSQL, Vault in unit tests
   - Use fixtures from `conftest.py`

---

## Next Steps

### 1. Run Tests Locally

```bash
pip install -r tests/requirements-test.txt
pytest tests/ -v --cov=. --cov-report=html
```

### 2. Review Coverage

```bash
open htmlcov/index.html
# Identify untested code paths
```

### 3. Add Integration Tests

Create `test_integration.py` for end-to-end tests with real services.

### 4. Set Up CI/CD

Add test automation to your deployment pipeline.

### 5. Monitor Coverage

Aim to maintain >80% coverage for critical code paths.

---

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python mocking guide](https://docs.python.org/3/library/unittest.mock.html)
- [MUTT README.md](../README.md)
- [MUTT HANDOFF.md](../HANDOFF.md)

---

## Test Maintenance

### When to Update Tests

- ✅ After fixing a bug (add regression test)
- ✅ When adding new features
- ✅ When changing business logic
- ✅ When refactoring (tests should still pass)

### Test Hygiene

- Run tests before committing: `pytest tests/ -v`
- Keep tests fast (unit tests should be <1s each)
- Fix failing tests immediately
- Remove obsolete tests when removing features

---

**Happy Testing! 🧪**
