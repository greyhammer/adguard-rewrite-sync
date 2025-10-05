"""
Kubernetes resource watching and DNS resource discovery
"""

import os
import threading
from typing import Dict
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from logger import logger


class KubernetesWatcher:
    """Watches Kubernetes resources for MetalLB IPs and hostnames"""
    
    def __init__(self):
        self.v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        
        # Configurable timeout for Kubernetes API watch operations
        self.watch_timeout = int(os.getenv('K8S_WATCH_TIMEOUT', '0'))
        
        # Validate configuration
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate Kubernetes client configuration"""
        if self.watch_timeout < 0 or self.watch_timeout > 3600:
            raise ValueError(f"K8S_WATCH_TIMEOUT must be between 0 and 3600 seconds, got {self.watch_timeout}")
        
        logger.info("Kubernetes client configuration validated",
                   watch_timeout=self.watch_timeout)
    
    def get_all_dns_resources(self) -> Dict[str, str]:
        """Get all DNS resources (hostname -> IP mappings) in a unified way"""
        dns_resources = {}
        
        try:
            # Get all services across all namespaces with field selector for LoadBalancer type
            service_list = self.v1.list_service_for_all_namespaces(
                field_selector='spec.type=LoadBalancer'
            )
            
            # First pass: collect LoadBalancer services and find Traefik IP
            traefik_ip = None
            
            for service in service_list.items:
                if (service.spec.type == "LoadBalancer" and 
                    service.status.load_balancer and 
                    service.status.load_balancer.ingress):
                    
                    for ingress in service.status.load_balancer.ingress:
                        if ingress.ip:
                            # Check if this is Traefik service
                            service_name = service.metadata.name.lower()
                            labels = service.metadata.labels or {}
                            
                            is_traefik = (
                                'traefik' in service_name or
                                labels.get('app') == 'traefik' or
                                labels.get('app.kubernetes.io/name') == 'traefik' or
                                'traefik' in str(labels)
                            )
                            
                            if is_traefik:
                                traefik_ip = ingress.ip
                                logger.info(f"Found Traefik LoadBalancer IP: {traefik_ip}")
                            else:
                                # Regular LoadBalancer service
                                annotations = service.metadata.annotations or {}
                                hostname = annotations.get('dns.sync/hostname')
                                
                                if hostname:
                                    dns_resources[hostname] = ingress.ip
                                    logger.info(f"Found LoadBalancer service with custom hostname: {hostname} -> {ingress.ip}")
                                else:
                                    # Use default hostname format
                                    default_hostname = f"{service.metadata.name}.{service.metadata.namespace}.svc.cluster.local"
                                    dns_resources[default_hostname] = ingress.ip
                                    logger.info(f"Found LoadBalancer service with default hostname: {default_hostname} -> {ingress.ip}")
            
            # Second pass: collect Traefik ingress hostnames
            if traefik_ip:
                try:
                    ingress_resources = self.networking_v1.list_ingress_for_all_namespaces()
                    
                    for ingress in ingress_resources.items:
                        # Check if it's using Traefik
                        ingress_class = ingress.spec.ingress_class_name
                        annotations = ingress.metadata.annotations or {}
                        
                        is_traefik = (
                            ingress_class == "traefik" or
                            "traefik.ingress.kubernetes.io" in str(annotations) or
                            annotations.get("kubernetes.io/ingress.class") == "traefik"
                        )
                        
                        if is_traefik and ingress.spec.rules:
                            for rule in ingress.spec.rules:
                                if rule.host:
                                    dns_resources[rule.host] = traefik_ip
                                    logger.info(f"Found Traefik ingress hostname: {rule.host} -> {traefik_ip}")
                except ApiException as e:
                    logger.error(f"Failed to get Traefik ingress: {e}")
            else:
                logger.warning("Traefik LoadBalancer IP not found - skipping ingress hostnames")
                            
        except ApiException as e:
            logger.error(f"Failed to get DNS resources: {e}")
        
        return dns_resources
    
    def watch_resources(self, callback):
        """Watch for changes in services and ingress resources"""
        def watch_services():
            """Watch service events"""
            service_watch = watch.Watch()
            try:
                for event in service_watch.stream(
                    self.v1.list_service_for_all_namespaces,
                    timeout_seconds=self.watch_timeout
                ):
                    if event['type'] in ['ADDED', 'MODIFIED', 'DELETED']:
                        service = event['object']
                        if service.spec.type == "LoadBalancer":
                            callback('service', event['type'], service)
            except Exception as e:
                logger.error(f"Service watch error: {e}")
        
        def watch_ingress():
            """Watch ingress events"""
            ingress_watch = watch.Watch()
            try:
                for event in ingress_watch.stream(
                    self.networking_v1.list_ingress_for_all_namespaces,
                    timeout_seconds=self.watch_timeout
                ):
                    if event['type'] in ['ADDED', 'MODIFIED', 'DELETED']:
                        ingress = event['object']
                        # Check if it's Traefik ingress
                        annotations = ingress.metadata.annotations or {}
                        is_traefik = (
                            ingress.spec.ingress_class_name == "traefik" or
                            "traefik.ingress.kubernetes.io" in str(annotations)
                        )
                        if is_traefik:
                            callback('ingress', event['type'], ingress)
            except Exception as e:
                logger.error(f"Ingress watch error: {e}")
        
        # Start both watchers in separate threads
        service_thread = threading.Thread(target=watch_services, daemon=True)
        ingress_thread = threading.Thread(target=watch_ingress, daemon=True)
        
        service_thread.start()
        ingress_thread.start()
        
        # Wait for both threads
        service_thread.join()
        ingress_thread.join()
