"""
Simplified and reliable health checking system
"""

import time
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from logger import logger


class HealthChecker:
    """Simplified health checker with caching and reliability improvements"""
    
    def __init__(self, adguard_client, k8s_watcher):
        self.adguard_client = adguard_client
        self.k8s_watcher = k8s_watcher
        
        # Health state with caching
        self._health_cache = {
            "adguard": {"healthy": False, "last_check": None, "error": None},
            "k8s": {"healthy": False, "last_check": None, "error": None}
        }
        
        # Configurable cache duration
        self.cache_duration = int(os.getenv('HEALTH_CACHE_DURATION', '30'))
        self._lock = threading.Lock()
        
        # Consecutive failure tracking
        self._consecutive_failures = {"adguard": 0, "k8s": 0}
        self.max_consecutive_failures = int(os.getenv('HEALTH_MAX_CONSECUTIVE_FAILURES', '3'))
        self.health_check_timeout = int(os.getenv('HEALTH_CHECK_TIMEOUT', '10'))
        
        # Validate configuration
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate health checker configuration"""
        if self.cache_duration < 5 or self.cache_duration > 300:
            raise ValueError(f"HEALTH_CACHE_DURATION must be between 5 and 300 seconds, got {self.cache_duration}")
        
        if self.max_consecutive_failures < 1 or self.max_consecutive_failures > 10:
            raise ValueError(f"HEALTH_MAX_CONSECUTIVE_FAILURES must be between 1 and 10, got {self.max_consecutive_failures}")
        
        if self.health_check_timeout < 1 or self.health_check_timeout > 60:
            raise ValueError(f"HEALTH_CHECK_TIMEOUT must be between 1 and 60 seconds, got {self.health_check_timeout}")
        
        logger.info("Health checker configuration validated",
                   cache_duration=self.cache_duration,
                   max_consecutive_failures=self.max_consecutive_failures,
                   health_check_timeout=self.health_check_timeout)
    
    def _is_cache_valid(self, component: str) -> bool:
        """Check if cached health data is still valid"""
        last_check = self._health_cache[component]["last_check"]
        if not last_check:
            return False
        
        return datetime.now() - last_check < timedelta(seconds=self.cache_duration)
    
    def _check_adguard_health(self) -> bool:
        """Check AdGuardHome connectivity with improved error handling"""
        try:
            start_time = time.time()
            response = self.adguard_client.session.get(
                f"{self.adguard_client.base_url}/control/status",
                timeout=self.health_check_timeout
            )
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                self._consecutive_failures["adguard"] = 0
                logger.adguard_api_call("health_check", True, duration_ms)
                return True
            else:
                error_msg = f"HTTP {response.status_code}"
                self._consecutive_failures["adguard"] += 1
                logger.adguard_api_call("health_check", False, duration_ms)
                logger.health_check("adguard", False, error_msg)
                return False
                
        except Exception as e:
            self._consecutive_failures["adguard"] += 1
            error_msg = str(e)
            logger.health_check("adguard", False, error_msg)
            return False
    
    def _check_k8s_health(self) -> bool:
        """Check Kubernetes connectivity with improved error handling"""
        try:
            start_time = time.time()
            # Simple namespace list check
            self.k8s_watcher.v1.list_namespace(limit=1)
            duration_ms = (time.time() - start_time) * 1000
            
            self._consecutive_failures["k8s"] = 0
            logger.health_check("k8s", True, f"API call successful ({duration_ms:.1f}ms)")
            return True
            
        except Exception as e:
            self._consecutive_failures["k8s"] += 1
            error_msg = str(e)
            logger.health_check("k8s", False, error_msg)
            return False
    
    def _update_health_cache(self, component: str, healthy: bool, error: Optional[str] = None):
        """Update health cache with thread safety"""
        with self._lock:
            self._health_cache[component] = {
                "healthy": healthy,
                "last_check": datetime.now(),
                "error": error
            }
    
    def check_adguard_connectivity(self) -> bool:
        """Check AdGuardHome connectivity with caching"""
        if self._is_cache_valid("adguard"):
            return self._health_cache["adguard"]["healthy"]
        
        healthy = self._check_adguard_health()
        self._update_health_cache("adguard", healthy)
        return healthy
    
    def check_k8s_connectivity(self) -> bool:
        """Check Kubernetes connectivity with caching"""
        if self._is_cache_valid("k8s"):
            return self._health_cache["k8s"]["healthy"]
        
        healthy = self._check_k8s_health()
        self._update_health_cache("k8s", healthy)
        return healthy
    
    def is_healthy(self) -> bool:
        """Check if system is overall healthy"""
        adguard_healthy = self.check_adguard_connectivity()
        k8s_healthy = self.check_k8s_connectivity()
        
        # Consider unhealthy if too many consecutive failures
        if (self._consecutive_failures["adguard"] >= self.max_consecutive_failures or
            self._consecutive_failures["k8s"] >= self.max_consecutive_failures):
            return False
        
        return adguard_healthy and k8s_healthy
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status with metrics"""
        adguard_healthy = self.check_adguard_connectivity()
        k8s_healthy = self.check_k8s_connectivity()
        overall_healthy = self.is_healthy()
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "adguard_healthy": adguard_healthy,
            "k8s_healthy": k8s_healthy,
            "adguard_last_check": self._health_cache["adguard"]["last_check"].isoformat() if self._health_cache["adguard"]["last_check"] else None,
            "k8s_last_check": self._health_cache["k8s"]["last_check"].isoformat() if self._health_cache["k8s"]["last_check"] else None,
            "adguard_error": self._health_cache["adguard"]["error"],
            "k8s_error": self._health_cache["k8s"]["error"],
            "consecutive_failures": self._consecutive_failures,
            "metrics": logger.get_metrics()
        }
    
    def force_refresh(self):
        """Force refresh of all health checks"""
        with self._lock:
            self._health_cache["adguard"]["last_check"] = None
            self._health_cache["k8s"]["last_check"] = None
