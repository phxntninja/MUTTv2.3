#!/usr/bin/env python3
"""
MUTT v2.5 - SLO Compliance Checker

This module provides functionality to query Prometheus for actual metrics
and compare them against defined SLO targets to determine compliance.

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Import SLO definitions
from slo_definitions import SLO_TARGETS, GLOBAL_SLO_SETTINGS

# Optional DynamicConfig
try:
    from dynamic_config import DynamicConfig
except ImportError:
    DynamicConfig = None

logger = logging.getLogger(__name__)


class SLOComplianceChecker:
    """
    Checks SLO compliance by querying Prometheus and comparing with targets.
    """

    def __init__(self, prometheus_url: str, dynamic_config: Optional[DynamicConfig] = None):
        self.prometheus_url = prometheus_url.rstrip('/')
        self.dynamic_config = dynamic_config
        self.slo_targets = SLO_TARGETS
        self.global_settings = GLOBAL_SLO_SETTINGS
        logger.info(f"SLOComplianceChecker initialized with Prometheus URL: {self.prometheus_url}")

    def _get_dynamic_setting(self, key: str, default: Any) -> Any:
        """Helper to get a setting from dynamic config or fallback to default."""
        if self.dynamic_config:
            try:
                value = self.dynamic_config.get(key, default=str(default))
                if isinstance(default, int):
                    return int(value)
                if isinstance(default, float):
                    return float(value)
                return value
            except Exception as e:
                logger.debug(f"Failed to get dynamic config for {key}: {e}")
        return default

    def _query_prometheus(self, expr: str, timeout: int = 5) -> Optional[float]:
        """
        Queries Prometheus HTTP API and returns a scalar value.
        Includes a single retry mechanism.
        """
        url = f"{self.prometheus_url}/api/v1/query"
        params = {"query": expr}
        for attempt in range(2): # Try twice
            try:
                response = requests.get(url, params=params, timeout=timeout)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                data = response.json()

                if data.get('status') != 'success':
                    logger.warning(f"Prometheus query failed (status: {data.get('status')}): {expr}")
                    return None

                result = data.get('data', {}).get('result', [])
                if not result:
                    logger.debug(f"Prometheus query returned no data: {expr}")
                    return None

                # Expecting a scalar value, so take the second element of the 'value' array
                value = result[0].get('value', [None, None])[1]
                return float(value) if value is not None else None

            except requests.exceptions.Timeout:
                logger.warning(f"Prometheus query timed out (attempt {attempt + 1}): {expr}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Prometheus connection error (attempt {attempt + 1}): {e}")
            except requests.exceptions.HTTPError as e:
                logger.warning(f"Prometheus HTTP error (attempt {attempt + 1}): {e}")
            except Exception as e:
                logger.error(f"Unexpected error during Prometheus query (attempt {attempt + 1}): {e}", exc_info=True)

            if attempt == 0: # Only sleep before the second attempt
                time.sleep(2) # Wait a bit before retrying

        return None

    def check_slo(self, slo_name: str) -> Dict[str, Any]:
        """
        Checks compliance for a single SLO.
        """
        slo_def = self.slo_targets.get(slo_name)
        if not slo_def:
            return {"slo_name": slo_name, "status": "error", "message": "SLO definition not found"}

        logger.debug(f"Checking SLO: {slo_name}")

        # Get dynamic settings or fallbacks
        window_hours = self._get_dynamic_setting(f"slo_{slo_name}_window_hours", slo_def.get("window_hours", self.global_settings["default_slo_window_hours"]))
        burn_rate_warning = self._get_dynamic_setting(f"slo_{slo_name}_burn_rate_warning", slo_def.get("burn_rate_threshold_warning", self.global_settings["default_burn_rate_warning"]))
        burn_rate_critical = self._get_dynamic_setting(f"slo_{slo_name}_burn_rate_critical", slo_def.get("burn_rate_threshold_critical", self.global_settings["default_burn_rate_critical"]))

        # Construct query with dynamic window
        metric_query = slo_def["metric_query"].replace("[5m]", f"[{window_hours}h]")
        target = slo_def.get("target")
        target_seconds = slo_def.get("target_seconds")

        actual_value = self._query_prometheus(metric_query)

        result: Dict[str, Any] = {
            "slo_name": slo_name,
            "description": slo_def["description"],
            "window_hours": window_hours,
            "metric_query": metric_query,
            "actual_value": actual_value,
            "status": "unknown",
            "error_budget_remaining": None,
            "burn_rate": None,
            "message": "No data from Prometheus" if actual_value is None else ""
        }

        if actual_value is None:
            return result

        if target is not None: # Availability/Success Rate SLO
            result["target"] = target
            if actual_value >= target:
                result["status"] = "ok"
                result["message"] = "Within target"
            else:
                result["status"] = "breaching"
                result["message"] = "Below target"

            # Calculate error budget and burn rate
            error_budget = max(0.0, 1.0 - target)
            error_rate = max(0.0, 1.0 - actual_value)
            burn_rate = (error_rate / error_budget) if error_budget > 0 else 0.0

            result["error_budget_remaining"] = (actual_value - target) / (1.0 - target) if (1.0 - target) > 0 else 1.0
            result["burn_rate"] = burn_rate

            if burn_rate >= burn_rate_critical:
                result["status"] = "critical"
                result["message"] = f"Critical burn rate ({burn_rate:.2f}x target)"
            elif burn_rate >= burn_rate_warning:
                result["status"] = "warning"
                result["message"] = f"Warning burn rate ({burn_rate:.2f}x target)"
            elif actual_value < target:
                result["status"] = "breaching"
                result["message"] = "Below target"
            else:
                result["status"] = "ok"
                result["message"] = "Within target"

        elif target_seconds is not None: # Latency SLO (upper bound)
            result["target_seconds"] = target_seconds
            if actual_value <= target_seconds:
                result["status"] = "ok"
                result["message"] = "Within target latency"
            else:
                result["status"] = "breaching"
                result["message"] = "Above target latency"

            # For latency, burn rate is often calculated differently or not at all in this context.
            # We can define simple thresholds for warning/critical based on absolute values.
            upper_bound_warning = self._get_dynamic_setting(f"slo_{slo_name}_upper_bound_warning", slo_def.get("upper_bound_threshold_warning", target_seconds * 1.5))
            upper_bound_critical = self._get_dynamic_setting(f"slo_{slo_name}_upper_bound_critical", slo_def.get("upper_bound_threshold_critical", target_seconds * 2.0))

            if actual_value >= upper_bound_critical:
                result["status"] = "critical"
                result["message"] = f"Critical latency ({actual_value:.3f}s > {upper_bound_critical:.3f}s)"
            elif actual_value >= upper_bound_warning:
                result["status"] = "warning"
                result["message"] = f"Warning latency ({actual_value:.3f}s > {upper_bound_warning:.3f}s)"
            elif actual_value > target_seconds:
                result["status"] = "breaching"
                result["message"] = "Above target latency"
            else:
                result["status"] = "ok"
                result["message"] = "Within target latency"

        return result

    def get_compliance_report(self) -> List[Dict[str, Any]]:
        """
        Generates a full SLO compliance report for all defined SLOs.
        """
        report = []
        for slo_name in self.slo_targets.keys():
            report.append(self.check_slo(slo_name))
        return report


def main():
    """Main entry point for CLI usage."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    prometheus_url = os.getenv('PROMETHEUS_URL', 'http://localhost:9090')
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))

    dynamic_config_instance = None
    if DynamicConfig:
        try:
            redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
            redis_client.ping()
            dynamic_config_instance = DynamicConfig(redis_client, prefix="mutt:config")
            logger.info("Connected to Redis for dynamic config.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis for dynamic config: {e}")

    checker = SLOComplianceChecker(prometheus_url, dynamic_config_instance)
    report = checker.get_compliance_report()

    print(json.dumps(report, indent=2))

    # Exit with non-zero code if any critical SLO is breaching
    for slo in report:
        if slo.get("status") == "critical":
            sys.exit(1)


if __name__ == "__main__":
    main()
