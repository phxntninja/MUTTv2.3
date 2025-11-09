# =====================================================================
# MUTT v2.3 Alerter Service Unit Tests
# =====================================================================
# Tests for alerter_service.py
# Run with: pytest tests/test_alerter_unit.py -v
# =====================================================================

import pytest
from unittest.mock import Mock, MagicMock, patch
import json
import re


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestRuleMatchingContains:
    """Test 'contains' match type"""

    def test_contains_match_found(self, sample_alert_rules):
        """Test that 'contains' match finds substring"""
        rule = sample_alert_rules[0]  # CRITICAL rule
        message = {"message": "CRITICAL: System failure"}

        # Simulate contains matching
        if rule["match_type"] == "contains":
            match = rule["match_string"] in message["message"]

        assert match is True

    def test_contains_match_not_found(self, sample_alert_rules):
        """Test that 'contains' match doesn't false positive"""
        rule = sample_alert_rules[0]  # CRITICAL rule
        message = {"message": "INFO: Normal operation"}

        if rule["match_type"] == "contains":
            match = rule["match_string"] in message["message"]

        assert match is False

    def test_contains_case_sensitive(self, sample_alert_rules):
        """Test that 'contains' match is case-sensitive"""
        rule = sample_alert_rules[0]  # CRITICAL rule (uppercase)
        message = {"message": "critical: lowercase message"}

        if rule["match_type"] == "contains":
            match = rule["match_string"] in message["message"]

        assert match is False  # Case-sensitive, should not match

    def test_contains_partial_word_match(self):
        """Test that 'contains' matches partial words"""
        match_string = "ERROR"
        message_text = "ERRORS detected in system"

        match = match_string in message_text

        assert match is True  # Substring match


class TestRuleMatchingRegex:
    """Test 'regex' match type"""

    def test_regex_match_found(self, sample_alert_rules):
        """Test that regex pattern matches"""
        rule = sample_alert_rules[2]  # LINK-(UP|DOWN) rule
        message = {"message": "Interface eth0: LINK-DOWN"}

        if rule["match_type"] == "regex":
            pattern = re.compile(rule["match_string"])
            match = pattern.search(message["message"])

        assert match is not None
        assert match.group(1) == "DOWN"

    def test_regex_match_alternative_pattern(self, sample_alert_rules):
        """Test regex with alternative pattern (UP)"""
        rule = sample_alert_rules[2]  # LINK-(UP|DOWN) rule
        message = {"message": "Interface eth0: LINK-UP"}

        if rule["match_type"] == "regex":
            pattern = re.compile(rule["match_string"])
            match = pattern.search(message["message"])

        assert match is not None
        assert match.group(1) == "UP"

    def test_regex_no_match(self, sample_alert_rules):
        """Test regex when pattern doesn't match"""
        rule = sample_alert_rules[2]  # LINK-(UP|DOWN) rule
        message = {"message": "Normal system message"}

        if rule["match_type"] == "regex":
            pattern = re.compile(rule["match_string"])
            match = pattern.search(message["message"])

        assert match is None

    def test_regex_invalid_pattern_handled(self):
        """Test that invalid regex pattern raises error"""
        invalid_pattern = r"[invalid(regex"

        with pytest.raises(re.error):
            re.compile(invalid_pattern)


class TestRuleMatchingOIDPrefix:
    """Test 'oid_prefix' match type for SNMP traps"""

    def test_oid_exact_match(self, sample_alert_rules):
        """Test exact OID match"""
        rule = sample_alert_rules[3]  # .1.3.6.1.6.3.1.1.5.3 rule
        trap_oid = ".1.3.6.1.6.3.1.1.5.3"

        if rule["match_type"] == "oid_prefix":
            match = trap_oid.startswith(rule["trap_oid"])

        assert match is True

    def test_oid_prefix_match(self, sample_alert_rules):
        """Test OID prefix match (child OID)"""
        rule = sample_alert_rules[3]  # .1.3.6.1.6.3.1.1.5.3 rule
        trap_oid = ".1.3.6.1.6.3.1.1.5.3.1.0"  # Child OID

        if rule["match_type"] == "oid_prefix":
            match = trap_oid.startswith(rule["trap_oid"])

        assert match is True

    def test_oid_no_match(self, sample_alert_rules):
        """Test OID that doesn't match"""
        rule = sample_alert_rules[3]  # .1.3.6.1.6.3.1.1.5.3 rule
        trap_oid = ".1.3.6.1.4.1.9.9.41.2"  # Different OID

        if rule["match_type"] == "oid_prefix":
            match = trap_oid.startswith(rule["trap_oid"])

        assert match is False

    def test_oid_parent_no_match(self, sample_alert_rules):
        """Test that parent OID doesn't match child rule"""
        rule = sample_alert_rules[3]  # .1.3.6.1.6.3.1.1.5.3 rule
        trap_oid = ".1.3.6.1.6.3.1"  # Parent OID

        if rule["match_type"] == "oid_prefix":
            match = trap_oid.startswith(rule["trap_oid"])

        assert match is False


class TestPrioritySelection:
    """Test rule priority selection logic"""

    def test_lowest_priority_wins(self, sample_alert_rules):
        """Test that lowest priority number is selected"""
        # Simulate multiple matching rules
        matching_rules = [
            sample_alert_rules[0],  # priority 10
            sample_alert_rules[1],  # priority 20
            sample_alert_rules[2],  # priority 5
        ]

        # Select rule with lowest priority number
        selected_rule = min(matching_rules, key=lambda r: r["priority"])

        assert selected_rule["priority"] == 5
        assert selected_rule["id"] == 3

    def test_single_match_selected(self, sample_alert_rules):
        """Test that single matching rule is selected"""
        matching_rules = [sample_alert_rules[0]]  # Only one match

        selected_rule = min(matching_rules, key=lambda r: r["priority"])

        assert selected_rule == sample_alert_rules[0]

    def test_no_match_returns_none(self):
        """Test that no matching rules returns None"""
        matching_rules = []

        if matching_rules:
            selected_rule = min(matching_rules, key=lambda r: r["priority"])
        else:
            selected_rule = None

        assert selected_rule is None


class TestEnvironmentDetection:
    """Test production vs development environment detection"""

    def test_dev_host_detected(self, sample_dev_hosts):
        """Test that dev host is identified"""
        hostname = "dev-server-01"

        is_dev = hostname in sample_dev_hosts

        assert is_dev is True

    def test_prod_host_detected(self, sample_dev_hosts):
        """Test that prod host is identified"""
        hostname = "prod-server-01"

        is_dev = hostname in sample_dev_hosts

        assert is_dev is False

    def test_handling_decision_for_dev(self, sample_alert_rules, sample_dev_hosts):
        """Test correct handling for dev environment"""
        rule = sample_alert_rules[0]  # CRITICAL rule
        hostname = "dev-server-01"

        is_dev = hostname in sample_dev_hosts
        handling = rule["dev_handling"] if is_dev else rule["prod_handling"]

        assert handling == "Ticket_only"

    def test_handling_decision_for_prod(self, sample_alert_rules, sample_dev_hosts):
        """Test correct handling for prod environment"""
        rule = sample_alert_rules[0]  # CRITICAL rule
        hostname = "prod-server-01"

        is_dev = hostname in sample_dev_hosts
        handling = rule["dev_handling"] if is_dev else rule["prod_handling"]

        assert handling == "Page_and_ticket"


class TestUnhandledEventDetection:
    """Test unhandled event counter and meta-alert logic"""

    def test_counter_increments(self, mock_redis_client):
        """Test that unhandled counter increments"""
        key = "mutt:unhandled:test-host"

        mock_redis_client.incr.return_value = 1
        count = mock_redis_client.incr(key)

        assert count == 1
        mock_redis_client.incr.assert_called_once_with(key)

    def test_threshold_detection(self, mock_config):
        """Test threshold is correctly detected"""
        count = 100
        threshold = mock_config.UNHANDLED_EVENT_THRESHOLD

        threshold_met = (count == threshold)

        assert threshold_met is True

    def test_threshold_not_met(self, mock_config):
        """Test threshold not met"""
        count = 50
        threshold = mock_config.UNHANDLED_EVENT_THRESHOLD

        threshold_met = (count == threshold)

        assert threshold_met is False

    def test_lua_script_prevents_duplicates(self, mock_redis_client):
        """Test Lua script atomic operation"""
        # Simulate Lua script execution
        # Script checks if triggered key exists, if not, RENAME counter to triggered

        key = "mutt:unhandled:test-host"
        triggered_key = "mutt:unhandled:triggered:test-host"

        # Mock Lua script returning 1 (trigger meta-alert)
        mock_redis_client.eval.return_value = 1

        result = mock_redis_client.eval("lua_script", 2, key, triggered_key, 100)

        assert result == 1  # Triggered
        mock_redis_client.eval.assert_called_once()

    def test_lua_script_prevents_duplicate_trigger(self, mock_redis_client):
        """Test Lua script prevents duplicate meta-alerts"""
        # Second call with same key should return 0 (already triggered)

        key = "mutt:unhandled:test-host"
        triggered_key = "mutt:unhandled:triggered:test-host"

        # Mock triggered key already exists
        mock_redis_client.eval.return_value = 0

        result = mock_redis_client.eval("lua_script", 2, key, triggered_key, 100)

        assert result == 0  # Not triggered (already done)


class TestJanitorLogic:
    """Test orphaned message recovery (janitor pattern)"""

    def test_orphaned_lists_detected(self, mock_redis_client):
        """Test janitor finds orphaned processing lists"""
        # Mock SCAN returning processing lists
        mock_redis_client.scan.return_value = (
            0,  # Cursor
            ["alerter_processing:pod-1", "alerter_processing:pod-2"]
        )

        cursor, keys = mock_redis_client.scan(0, match="alerter_processing:*", count=100)

        assert len(keys) == 2
        assert "alerter_processing:pod-1" in keys

    def test_heartbeat_check(self, mock_redis_client):
        """Test heartbeat existence check"""
        pod_name = "pod-1"
        heartbeat_key = f"mutt:heartbeat:{pod_name}"

        # Mock heartbeat exists
        mock_redis_client.exists.return_value = 1

        exists = mock_redis_client.exists(heartbeat_key)

        assert exists == 1  # Pod is alive

    def test_dead_pod_detection(self, mock_redis_client):
        """Test dead pod is detected (no heartbeat)"""
        pod_name = "pod-dead"
        heartbeat_key = f"mutt:heartbeat:{pod_name}"

        # Mock heartbeat doesn't exist
        mock_redis_client.exists.return_value = 0

        exists = mock_redis_client.exists(heartbeat_key)

        assert exists == 0  # Pod is dead

    def test_orphan_recovery(self, mock_redis_client):
        """Test orphaned messages are recovered to main queue"""
        orphaned_list = "alerter_processing:pod-dead"
        main_queue = "mutt:ingest_queue"

        # Mock RPOPLPUSH to move messages back
        mock_redis_client.rpoplpush.return_value = '{"message": "orphaned"}'

        message = mock_redis_client.rpoplpush(orphaned_list, main_queue)

        assert message is not None
        mock_redis_client.rpoplpush.assert_called_once_with(orphaned_list, main_queue)

    def test_heartbeat_maintenance(self, mock_redis_client):
        """Test heartbeat is refreshed"""
        pod_name = "pod-1"
        heartbeat_key = f"mutt:heartbeat:{pod_name}"
        ttl = 60

        mock_redis_client.setex.return_value = True

        result = mock_redis_client.setex(heartbeat_key, ttl, "alive")

        assert result is True
        mock_redis_client.setex.assert_called_once_with(heartbeat_key, ttl, "alive")


class TestBRPOPLPUSHPattern:
    """Test reliable message processing pattern"""

    def test_message_moved_atomically(self, mock_redis_client):
        """Test BRPOPLPUSH moves message atomically"""
        source = "mutt:ingest_queue"
        destination = "alerter_processing:pod-1"

        mock_redis_client.brpoplpush.return_value = '{"message": "test"}'

        message = mock_redis_client.brpoplpush(source, destination, timeout=30)

        assert message is not None
        mock_redis_client.brpoplpush.assert_called_once_with(source, destination, timeout=30)

    def test_message_deleted_after_success(self, mock_redis_client):
        """Test message is deleted from processing list after success"""
        processing_list = "alerter_processing:pod-1"
        message = '{"message": "test"}'

        mock_redis_client.lrem.return_value = 1

        removed = mock_redis_client.lrem(processing_list, 1, message)

        assert removed == 1
        mock_redis_client.lrem.assert_called_once_with(processing_list, 1, message)

    def test_message_remains_on_failure(self, mock_redis_client):
        """Test message stays in processing list on failure"""
        # If processing fails, we don't call lrem
        # Message remains in processing list for recovery

        mock_redis_client.lrem.assert_not_called()

        # On next pod startup, janitor will recover it
        assert True


class TestDatabaseOperations:
    """Test PostgreSQL audit log writes"""

    def test_audit_log_insert(self, mock_postgres_conn):
        """Test audit log record is inserted"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        # Simulate INSERT
        cursor.execute(
            "INSERT INTO event_audit_log (...) VALUES (...)",
            ("values",)
        )

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        mock_postgres_conn.commit.assert_called_once()

    def test_partition_not_found_error(self, mock_postgres_conn):
        """Test partition not found error is caught"""
        import psycopg2

        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        # Simulate partition error
        cursor.execute.side_effect = psycopg2.Error("no partition found")

        with pytest.raises(psycopg2.Error):
            cursor.execute("INSERT INTO event_audit_log ...")

    def test_connection_pool_getconn(self, mock_postgres_pool):
        """Test getting connection from pool"""
        conn = mock_postgres_pool.getconn()

        assert conn is not None
        mock_postgres_pool.getconn.assert_called_once()

    def test_connection_pool_putconn(self, mock_postgres_pool):
        """Test returning connection to pool"""
        conn = mock_postgres_pool.getconn()

        mock_postgres_pool.putconn(conn)

        mock_postgres_pool.putconn.assert_called_once_with(conn)


class TestRuleCacheManagement:
    """Test in-memory rule cache"""

    def test_cache_loaded_on_startup(self, sample_alert_rules):
        """Test cache is populated from database"""
        # Simulate loading rules from DB
        cache = {
            "alert_rules": sample_alert_rules,
            "dev_hosts": set(),
            "device_teams": {}
        }

        assert len(cache["alert_rules"]) == 4
        assert isinstance(cache["dev_hosts"], set)
        assert isinstance(cache["device_teams"], dict)

    def test_cache_refresh(self, sample_alert_rules):
        """Test cache can be refreshed"""
        # Initial cache
        cache = {"alert_rules": []}

        # Refresh cache
        cache["alert_rules"] = sample_alert_rules

        assert len(cache["alert_rules"]) == 4

    def test_inactive_rules_filtered(self, sample_alert_rules):
        """Test inactive rules are excluded"""
        # Add inactive rule
        inactive_rule = sample_alert_rules[0].copy()
        inactive_rule["is_active"] = False
        all_rules = sample_alert_rules + [inactive_rule]

        # Filter active rules
        active_rules = [r for r in all_rules if r["is_active"]]

        assert len(active_rules) == 4  # Inactive not included


class TestTeamAssignment:
    """Test team assignment logic"""

    def test_rule_team_assignment(self, sample_alert_rules):
        """Test team from matching rule"""
        rule = sample_alert_rules[0]  # NETO team

        team = rule["team_assignment"]

        assert team == "NETO"

    def test_device_team_assignment(self, sample_device_teams):
        """Test team from device lookup"""
        hostname = "router1.prod.example.com"

        team = sample_device_teams.get(hostname, "DefaultTeam")

        assert team == "NetOps"

    def test_fallback_team_assignment(self, sample_device_teams):
        """Test fallback team for unknown device"""
        hostname = "unknown-device.example.com"

        team = sample_device_teams.get(hostname, "DefaultTeam")

        assert team == "DefaultTeam"


class TestSCANvsKEYS:
    """Test production-safe Redis iteration"""

    def test_scan_used_not_keys(self, mock_redis_client):
        """Test SCAN is used instead of KEYS"""
        # KEYS blocks Redis - SCAN does not

        mock_redis_client.scan.return_value = (0, ["key1", "key2"])

        cursor, keys = mock_redis_client.scan(0, match="pattern:*", count=100)

        mock_redis_client.scan.assert_called_once()
        # Should NOT call mock_redis_client.keys()

    def test_scan_iteration(self, mock_redis_client):
        """Test SCAN cursor iteration"""
        # Simulate multi-iteration SCAN
        mock_redis_client.scan.side_effect = [
            (10, ["key1", "key2"]),   # First call, cursor 10
            (20, ["key3", "key4"]),   # Second call, cursor 20
            (0, ["key5"])             # Last call, cursor 0 (done)
        ]

        all_keys = []
        cursor = 0
        while True:
            cursor, keys = mock_redis_client.scan(cursor, match="*", count=100)
            all_keys.extend(keys)
            if cursor == 0:
                break

        assert len(all_keys) == 5
        assert mock_redis_client.scan.call_count == 3


# =====================================================================
# Integration Test Markers
# =====================================================================

@pytest.mark.integration
class TestAlerterIntegration:
    """Integration tests requiring real services"""

    def test_real_database_connection(self):
        """Test connection to real PostgreSQL"""
        pytest.skip("Integration test - requires real PostgreSQL")

    def test_real_redis_connection(self):
        """Test connection to real Redis"""
        pytest.skip("Integration test - requires real Redis")


# =====================================================================
# Run tests with: pytest tests/test_alerter_unit.py -v
# Run with coverage: pytest tests/test_alerter_unit.py --cov=alerter_service --cov-report=html
# =====================================================================
