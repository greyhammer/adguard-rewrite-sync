"""
Enhanced logging system with structured logging and configurable levels
"""

import os
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


class Logger:
    """Enhanced logger with structured logging and metrics"""
    
    def __init__(self, name: str = "adguard-sync"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logging()
        self._metrics = {
            "sync_operations": 0,
            "rules_created": 0,
            "rules_updated": 0,
            "rules_deleted": 0,
            "errors": 0,
            "warnings": 0
        }
    
    def _setup_logging(self):
        """Setup logging configuration"""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set log level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Console handler for human-readable output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ConsoleFormatter())
        self.logger.addHandler(console_handler)
        
        # JSON handler for structured logging (if enabled)
        if os.getenv('JSON_LOGGING', 'false').lower() == 'true':
            json_handler = logging.StreamHandler(sys.stderr)
            json_handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(json_handler)
        
        # Prevent duplicate logs
        self.logger.propagate = False
    
    def _log_with_extra(self, level: int, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Log with extra structured fields"""
        if extra_fields:
            self.logger.log(level, message, extra={'extra_fields': extra_fields})
        else:
            self.logger.log(level, message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional extra fields"""
        self._log_with_extra(logging.DEBUG, message, kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with optional extra fields"""
        self._log_with_extra(logging.INFO, message, kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional extra fields"""
        self._metrics["warnings"] += 1
        self._log_with_extra(logging.WARNING, message, kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with optional extra fields"""
        self._metrics["errors"] += 1
        self._log_with_extra(logging.ERROR, message, kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with optional extra fields"""
        self._metrics["errors"] += 1
        self._log_with_extra(logging.CRITICAL, message, kwargs)
    
    def sync_start(self, rule_count: int):
        """Log sync operation start"""
        self._metrics["sync_operations"] += 1
        self.info(f"Starting DNS sync operation", 
                 operation="sync_start", 
                 rule_count=rule_count)
    
    def sync_success(self, rules_created: int, rules_updated: int, rules_deleted: int):
        """Log successful sync operation"""
        self._metrics["rules_created"] += rules_created
        self._metrics["rules_updated"] += rules_updated
        self._metrics["rules_deleted"] += rules_deleted
        
        self.info("DNS sync completed successfully",
                 operation="sync_success",
                 rules_created=rules_created,
                 rules_updated=rules_updated,
                 rules_deleted=rules_deleted)
    
    def sync_error(self, error: str, rule_count: int = 0):
        """Log sync operation error"""
        self.error(f"DNS sync failed: {error}",
                  operation="sync_error",
                  rule_count=rule_count)
    
    def rule_created(self, domain: str, ip: str):
        """Log rule creation"""
        self.info(f"Created DNS rule: {domain} -> {ip}",
                 operation="rule_created",
                 domain=domain,
                 ip=ip)
    
    def rule_updated(self, domain: str, old_ip: str, new_ip: str):
        """Log rule update"""
        self.info(f"Updated DNS rule: {domain} {old_ip} -> {new_ip}",
                 operation="rule_updated",
                 domain=domain,
                 old_ip=old_ip,
                 new_ip=new_ip)
    
    def rule_deleted(self, domain: str):
        """Log rule deletion"""
        self.info(f"Deleted DNS rule: {domain}",
                 operation="rule_deleted",
                 domain=domain)
    
    def k8s_resource_found(self, resource_type: str, name: str, namespace: str, ip: str = None):
        """Log Kubernetes resource discovery"""
        self.info(f"Found {resource_type}: {name} in {namespace}",
                 operation="k8s_resource_found",
                 resource_type=resource_type,
                 name=name,
                 namespace=namespace,
                 ip=ip)
    
    def adguard_api_call(self, operation: str, success: bool, duration_ms: float = None):
        """Log AdGuard API call"""
        level = logging.INFO if success else logging.ERROR
        message = f"AdGuard API {operation}: {'success' if success else 'failed'}"
        
        extra_fields = {
            "operation": "adguard_api_call",
            "api_operation": operation,
            "success": success
        }
        
        if duration_ms is not None:
            extra_fields["duration_ms"] = duration_ms
        
        if not success:
            self._metrics["errors"] += 1
        
        self._log_with_extra(level, message, extra_fields)
    
    def health_check(self, component: str, healthy: bool, details: str = None):
        """Log health check result"""
        level = logging.INFO if healthy else logging.WARNING
        message = f"Health check {component}: {'healthy' if healthy else 'unhealthy'}"
        
        extra_fields = {
            "operation": "health_check",
            "component": component,
            "healthy": healthy
        }
        
        if details:
            extra_fields["details"] = details
        
        self._log_with_extra(level, message, extra_fields)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return {
            **self._metrics,
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds() if hasattr(self, '_start_time') else 0
        }
    
    def reset_metrics(self):
        """Reset metrics counters"""
        for key in self._metrics:
            self._metrics[key] = 0
    
    def set_start_time(self):
        """Set application start time for uptime calculation"""
        self._start_time = datetime.now()


# Global logger instance
logger = Logger()
