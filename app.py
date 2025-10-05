#!/usr/bin/env python3
"""
Simplified AdGuardHome DNS Sync Application

A streamlined Kubernetes application that automatically manages AdGuardHome 
rewrite rules based on MetalLB LoadBalancer services and Traefik ingress resources.
"""

import os
import json
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict

from kubernetes import config
from k8s_client import KubernetesWatcher
from models import RewriteRule
from adguard_client import AdGuardHomeClientV2
from health import HealthChecker
from database import RuleDatabase
from logger import logger
from exceptions import ConfigurationError, AuthenticationError


class AdGuardDNSSync:
    """Simplified main application class"""
    
    def __init__(self):
        # Configuration
        self.adguard_url = os.getenv('ADGUARD_URL', 'http://adguard:3000')
        self.adguard_username = os.getenv('ADGUARD_USERNAME', 'admin')
        self.adguard_password = os.getenv('ADGUARD_PASSWORD', '')
        self.sync_interval = int(os.getenv('SYNC_INTERVAL', '30'))
        self.change_wait_time = int(os.getenv('APP_CHANGE_WAIT_TIME', '5'))
        self.main_loop_sleep = int(os.getenv('APP_MAIN_LOOP_SLEEP', '1'))
        self.thread_join_timeout = int(os.getenv('APP_THREAD_JOIN_TIMEOUT', '5'))
        self.health_server_port = int(os.getenv('APP_HEALTH_SERVER_PORT', '8080'))
        
        # Validate configuration
        self._validate_configuration()
        
        # Threading
        self.shutdown_event = threading.Event()
        self.threads = []
        
        # Initialize components
        self._setup_logging()
        self._setup_kubernetes()
        self._setup_adguard()
        self._setup_database()
        self._setup_health_checker()
        
        logger.set_start_time()
        logger.info("AdGuard DNS Sync application initialized")
        logger.warning("SAFETY: This application will ONLY manage rules it creates. It will NOT delete manually created rules.")
    
    def _validate_configuration(self):
        """Validate application configuration"""
        if self.sync_interval < 5 or self.sync_interval > 3600:
            raise ValueError(f"SYNC_INTERVAL must be between 5 and 3600 seconds, got {self.sync_interval}")
        
        if self.change_wait_time < 1 or self.change_wait_time > 60:
            raise ValueError(f"APP_CHANGE_WAIT_TIME must be between 1 and 60 seconds, got {self.change_wait_time}")
        
        if self.main_loop_sleep < 1 or self.main_loop_sleep > 10:
            raise ValueError(f"APP_MAIN_LOOP_SLEEP must be between 1 and 10 seconds, got {self.main_loop_sleep}")
        
        if self.thread_join_timeout < 1 or self.thread_join_timeout > 30:
            raise ValueError(f"APP_THREAD_JOIN_TIMEOUT must be between 1 and 30 seconds, got {self.thread_join_timeout}")
        
        if self.health_server_port < 1024 or self.health_server_port > 65535:
            raise ValueError(f"APP_HEALTH_SERVER_PORT must be between 1024 and 65535, got {self.health_server_port}")
        
        logger.info("Application configuration validated",
                   sync_interval=self.sync_interval,
                   change_wait_time=self.change_wait_time,
                   main_loop_sleep=self.main_loop_sleep,
                   thread_join_timeout=self.thread_join_timeout,
                   health_server_port=self.health_server_port)
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logger.info(f"Logging configured at {log_level} level")
    
    def _setup_kubernetes(self):
        """Setup Kubernetes client"""
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except Exception:
            try:
                kubeconfig_path = os.getenv('KUBECONFIG')
                if kubeconfig_path and os.path.exists(kubeconfig_path):
                    config.load_kube_config(config_file=kubeconfig_path)
                    logger.info(f"Loaded Kubernetes config from {kubeconfig_path}")
                else:
                    config.load_kube_config()
                    logger.info("Loaded default Kubernetes config")
            except Exception as e:
                logger.error(f"Failed to load Kubernetes config: {e}")
                raise
        
        self.k8s_watcher = KubernetesWatcher()
        logger.info("Kubernetes client initialized")
    
    def _setup_adguard(self):
        """Setup AdGuardHome client"""
        if not self.adguard_password:
            raise ConfigurationError("ADGUARD_PASSWORD environment variable is required")
        
        self.adguard = AdGuardHomeClientV2(
            self.adguard_url,
            self.adguard_username,
            self.adguard_password
        )
        logger.info("AdGuardHome client initialized")
    
    def _setup_database(self):
        """Setup rule database"""
        self.rule_db_file = "/app/data/managed_rules.json"
        self.rule_db = RuleDatabase(self.rule_db_file)
        logger.info("Rule database initialized")
    
    def _setup_health_checker(self):
        """Setup health checker"""
        self.health_checker = HealthChecker(self.adguard, self.k8s_watcher)
        logger.info("Health checker initialized")
    
    def get_dns_resources(self) -> Dict[str, str]:
        """Get all DNS resources from Kubernetes"""
        try:
            dns_resources = self.k8s_watcher.get_all_dns_resources()
            logger.info(f"Found {len(dns_resources)} DNS resources", 
                      resource_count=len(dns_resources))
            
            for hostname, ip in dns_resources.items():
                logger.k8s_resource_found("dns_resource", hostname, "cluster", ip)
            
            return dns_resources
            
        except Exception as e:
            logger.error(f"Failed to get DNS resources: {e}")
            return {}
    
    def generate_rules(self) -> Dict[str, RewriteRule]:
        """Generate rewrite rules from DNS resources"""
        dns_resources = self.get_dns_resources()
        rules = {}
        
        for hostname, ip in dns_resources.items():
            rule = RewriteRule(
                domain=hostname,
                answer=ip,
                enabled=True
            )
            rules[hostname] = rule
        
        logger.info(f"Generated {len(rules)} rewrite rules", rule_count=len(rules))
        return rules
    
    def sync_rules(self) -> bool:
        """Sync rules with AdGuardHome - SAFE approach"""
        try:
            # Generate current rules
            new_rules = self.generate_rules()
            
            # Load previously managed rules
            managed_rules = self.rule_db.load_managed_rules()
            
            # Sync with AdGuardHome - SAFE: only manage our rules
            success = self.adguard.sync_rules(new_rules, managed_rules)
            
            if success:
                # Save managed rules
                self.rule_db.save_managed_rules(new_rules)
                logger.info("Rule sync completed successfully")
            else:
                logger.error("Rule sync failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Rule sync error: {e}")
            return False
    
    def handle_resource_change(self, resource_type: str, event_type: str, resource):
        """Handle Kubernetes resource changes"""
        resource_name = f"{resource.metadata.name}.{resource.metadata.namespace}"
        logger.info(f"Resource change detected", 
                   resource_type=resource_type,
                   event_type=event_type,
                   resource_name=resource_name)
        
        # Trigger sync after a short delay to batch changes
        self._schedule_sync()
    
    def _schedule_sync(self):
        """Schedule a delayed sync to batch multiple changes"""
        def delayed_sync():
            time.sleep(self.change_wait_time)  # Wait for potential additional changes
            self.sync_rules()
        
        sync_thread = threading.Thread(target=delayed_sync, daemon=True)
        sync_thread.start()
    
    def start_health_server(self):
        """Start HTTP health check server"""
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health':
                    try:
                        health_data = self.server.app.health_checker.get_health_status()
                        
                        if health_data["status"] == "healthy":
                            self.send_response(200)
                        else:
                            self.send_response(503)
                        
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(health_data, indent=2).encode())
                        
                    except Exception as e:
                        logger.error(f"Health check error: {e}")
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        error_response = {
                            "status": "error",
                            "timestamp": datetime.now().isoformat(),
                            "error": str(e)
                        }
                        self.wfile.write(json.dumps(error_response).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                pass  # Suppress default logging
        
        def run_server():
            server = HTTPServer(('0.0.0.0', self.health_server_port), HealthHandler)
            server.app = self
            logger.info(f"Health check server started on port {self.health_server_port}")
            server.serve_forever()
        
        health_thread = threading.Thread(target=run_server, daemon=True, name="health-server")
        self.threads.append(health_thread)
        health_thread.start()
    
    def start_periodic_sync(self):
        """Start periodic sync thread"""
        def periodic_sync():
            while not self.shutdown_event.is_set():
                if self.shutdown_event.wait(self.sync_interval):
                    break
                
                logger.info(f"Starting periodic sync (interval: {self.sync_interval}s)")
                self.sync_rules()
        
        sync_thread = threading.Thread(target=periodic_sync, daemon=True, name="periodic-sync")
        self.threads.append(sync_thread)
        sync_thread.start()
    
    def start_k8s_watcher(self):
        """Start Kubernetes resource watcher"""
        def watch_resources():
            try:
                self.k8s_watcher.watch_resources(self.handle_resource_change)
            except Exception as e:
                logger.error(f"Kubernetes watcher error: {e}")
        
        watch_thread = threading.Thread(target=watch_resources, daemon=True, name="k8s-watcher")
        self.threads.append(watch_thread)
        watch_thread.start()
    
    def run(self):
        """Main application loop"""
        logger.info("Starting AdGuard DNS Sync application")
        
        # Start health server
        self.start_health_server()
        
        # Initial sync
        logger.info("Performing initial rule sync")
        self.sync_rules()
        
        # Start background threads
        self.start_periodic_sync()
        self.start_k8s_watcher()
        
        logger.info("Application started successfully")
        
        try:
            # Keep main thread alive
            while not self.shutdown_event.is_set():
                time.sleep(self.main_loop_sleep)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.shutdown()
        except Exception as e:
            logger.error(f"Application error: {e}")
            self.shutdown()
            raise
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Initiating graceful shutdown")
        self.shutdown_event.set()
        
        # Wait for threads to finish
        for thread in self.threads:
            if thread.is_alive():
                logger.info(f"Waiting for thread {thread.name} to finish")
                thread.join(timeout=self.thread_join_timeout)
        
        logger.info("Graceful shutdown completed")


def main():
    """Main entry point"""
    try:
        # Validate configuration
        if not os.getenv('ADGUARD_PASSWORD'):
            raise ConfigurationError("ADGUARD_PASSWORD environment variable is required")
        
        # Initialize and run application
        app = AdGuardDNSSync()
        app.run()
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        exit(1)
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        exit(1)


if __name__ == "__main__":
    # Configure logging early
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Print startup information
    print(f"=== AdGuardHome DNS Sync Application ===")
    print(f"Log level: {log_level}")
    print(f"AdGuard URL: {os.getenv('ADGUARD_URL', 'NOT SET')}")
    print(f"Sync interval: {os.getenv('SYNC_INTERVAL', '30')}s")
    print(f"=======================================")
    
    main()
