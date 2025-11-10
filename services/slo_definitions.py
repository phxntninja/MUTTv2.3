#!/usr/bin/env python3
"""
MUTT v2.5 - SLO Definitions

This module defines the Service Level Objectives (SLOs) for key MUTT components.
These definitions are used by the SLO compliance checker and dashboard.

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

from typing import Dict, Any

# Define SLO targets for various components
# These values can be overridden by dynamic configuration
SLO_TARGETS: Dict[str, Dict[str, Any]] = {
    "ingestor_availability": {
        "description": "Availability of the Ingestor Service (successful requests)",
        "target": 0.999,  # 99.9% availability
        "metric_query": "sum(rate(mutt_ingest_requests_total{status='success'}[5m])) / sum(rate(mutt_ingest_requests_total[5m]))",
        "window_hours": 24,
        "burn_rate_threshold_warning": 5, # 5x burn rate for warning
        "burn_rate_threshold_critical": 10 # 10x burn rate for critical
    },
    "ingestor_latency_p99": {
        "description": "P99 latency of Ingestor Service requests",
        "target_seconds": 0.5, # 500ms
        "metric_query": "histogram_quantile(0.99, sum(rate(mutt_ingest_latency_seconds_bucket[5m])) by (le))",
        "window_hours": 24,
        "upper_bound_threshold_warning": 0.75, # 750ms
        "upper_bound_threshold_critical": 1.0 # 1000ms
    },
    "forwarder_availability": {
        "description": "Availability of the Moog Forwarder Service (successful forwards)",
        "target": 0.995, # 99.5% availability
        "metric_query": "sum(rate(mutt_moog_requests_total{status='success'}[5m])) / sum(rate(mutt_moog_requests_total[5m]))",
        "window_hours": 24,
        "burn_rate_threshold_warning": 5,
        "burn_rate_threshold_critical": 10
    },
    "forwarder_latency_p99": {
        "description": "P99 latency of Moog Forwarder requests to Moogsoft",
        "target_seconds": 2.0, # 2000ms
        "metric_query": "histogram_quantile(0.99, sum(rate(mutt_moog_request_latency_seconds_bucket[5m])) by (le))",
        "window_hours": 24,
        "upper_bound_threshold_warning": 3.0,
        "upper_bound_threshold_critical": 5.0
    },
    "alerter_processing_success": {
        "description": "Success rate of Alerter event processing",
        "target": 0.999, # 99.9% success
        "metric_query": "sum(rate(mutt_alerter_events_processed_total{status='handled'}[5m])) / sum(rate(mutt_alerter_events_processed_total[5m]))",
        "window_hours": 24,
        "burn_rate_threshold_warning": 5,
        "burn_rate_threshold_critical": 10
    },
    "alerter_cache_reload_success": {
        "description": "Success rate of Alerter cache reloads",
        "target": 0.99, # 99% success
        "metric_query": "sum(rate(mutt_alerter_cache_reload_failures_total[5m])) == 0", # 0 failures
        "window_hours": 24,
        "burn_rate_threshold_warning": 5,
        "burn_rate_threshold_critical": 10
    }
}

# You can also define global SLO settings here if needed
GLOBAL_SLO_SETTINGS: Dict[str, Any] = {
    "default_slo_window_hours": 24,
    "default_burn_rate_warning": 5,
    "default_burn_rate_critical": 10
}

if __name__ == "__main__":
    print("MUTT v2.5 SLO Definitions")
    print("=" * 60)
    print("\nDefined SLO Targets:")
    for slo_name, slo_def in SLO_TARGETS.items():
        print(f"\n- {slo_name}:")
        for key, value in slo_def.items():
            print(f"  {key}: {value}")
    print("\nGlobal SLO Settings:")
    for key, value in GLOBAL_SLO_SETTINGS.items():
        print(f"- {key}: {value}")
