"""
Simplified and reliable AdGuardHome API client
"""

import os
import time
import requests
from typing import Dict, List, Optional
from models import RewriteRule
from logger import logger
from exceptions import AuthenticationError


class AdGuardHomeClientV2:
    """Simplified AdGuardHome client with improved reliability"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        
        # Configurable retry configuration
        self.max_retries = int(os.getenv('ADGUARD_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('ADGUARD_RETRY_DELAY', '2'))
        self.request_timeout = int(os.getenv('ADGUARD_REQUEST_TIMEOUT', '10'))
        self.safety_threshold = float(os.getenv('ADGUARD_SAFETY_THRESHOLD', '0.8'))
        
        # Validate configuration
        self._validate_configuration()
        
        logger.info("Initializing AdGuardHome client", 
                   base_url=self.base_url, 
                   username=self.username)
        
        self._authenticate()
    
    def _validate_configuration(self):
        """Validate AdGuardHome client configuration"""
        if self.max_retries < 1 or self.max_retries > 10:
            raise ValueError(f"ADGUARD_MAX_RETRIES must be between 1 and 10, got {self.max_retries}")
        
        if self.retry_delay < 1 or self.retry_delay > 60:
            raise ValueError(f"ADGUARD_RETRY_DELAY must be between 1 and 60 seconds, got {self.retry_delay}")
        
        if self.request_timeout < 1 or self.request_timeout > 300:
            raise ValueError(f"ADGUARD_REQUEST_TIMEOUT must be between 1 and 300 seconds, got {self.request_timeout}")
        
        if self.safety_threshold < 0.1 or self.safety_threshold > 1.0:
            raise ValueError(f"ADGUARD_SAFETY_THRESHOLD must be between 0.1 and 1.0, got {self.safety_threshold}")
        
        logger.info("AdGuardHome client configuration validated",
                   max_retries=self.max_retries,
                   retry_delay=self.retry_delay,
                   request_timeout=self.request_timeout,
                   safety_threshold=self.safety_threshold)
    
    def _authenticate(self):
        """Authenticate with AdGuardHome API"""
        auth_url = f"{self.base_url}/control/login"
        auth_data = {
            "name": self.username,
            "password": self.password
        }
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = self.session.post(auth_url, json=auth_data, timeout=self.request_timeout)
                duration_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    logger.adguard_api_call("authenticate", True, duration_ms)
                    logger.info("Successfully authenticated with AdGuardHome")
                    return
                else:
                    logger.adguard_api_call("authenticate", False, duration_ms)
                    logger.error(f"Authentication failed: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.adguard_api_call("authenticate", False)
                logger.error(f"Authentication attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        
        raise AuthenticationError("Failed to authenticate with AdGuardHome after all retries")
    
    def get_rewrite_rules(self) -> Dict[str, RewriteRule]:
        """Get all rewrite rules from AdGuardHome"""
        try:
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/control/rewrite/list", timeout=self.request_timeout)
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                logger.adguard_api_call("get_rules", False, duration_ms)
                return {}
            
            data = response.json()
            if not isinstance(data, list):
                logger.error(f"Expected list from AdGuardHome API, got {type(data)}")
                return {}
            
            rules = {}
            for rule_data in data:
                if isinstance(rule_data, dict) and all(key in rule_data for key in ['domain', 'answer']):
                    rule = RewriteRule(
                        domain=rule_data.get("domain", ""),
                        answer=rule_data.get("answer", ""),
                        enabled=rule_data.get("enabled", True)
                    )
                    rules[rule.domain] = rule
            
            logger.adguard_api_call("get_rules", True, duration_ms)
            logger.debug(f"Retrieved {len(rules)} rewrite rules from AdGuardHome")
            return rules
            
        except Exception as e:
            logger.adguard_api_call("get_rules", False)
            logger.error(f"Failed to get rewrite rules: {e}")
            return {}
    
    def add_rewrite_rule(self, rule: RewriteRule) -> bool:
        """Add a new rewrite rule"""
        return self._make_rule_request("add", rule)
    
    def delete_rewrite_rule(self, domain: str, current_rules: Dict[str, RewriteRule] = None) -> bool:
        """Delete a rewrite rule by domain"""
        # Get current rule to get the answer field
        if current_rules is None:
            current_rules = self.get_rewrite_rules()
        
        if domain not in current_rules:
            logger.info(f"Rule {domain} not found, nothing to delete")
            return True
        
        rule = current_rules[domain]
        payload = {
            "domain": domain,
            "answer": rule.answer
        }
        
        return self._make_rule_request("delete", payload)
    
    def update_rewrite_rule(self, rule: RewriteRule, current_rules: Dict[str, RewriteRule] = None) -> bool:
        """Update an existing rewrite rule"""
        # Get current rule to get the old answer
        if current_rules is None:
            current_rules = self.get_rewrite_rules()
        
        if rule.domain not in current_rules:
            logger.info(f"Rule {rule.domain} not found, adding as new rule")
            return self.add_rewrite_rule(rule)
        
        old_rule = current_rules[rule.domain]
        payload = {
            "target": {
                "domain": rule.domain,
                "answer": old_rule.answer
            },
            "update": {
                "domain": rule.domain,
                "answer": rule.answer
            }
        }
        
        return self._make_rule_request("update", payload)
    
    def _make_rule_request(self, operation: str, payload) -> bool:
        """Make a rule operation request with retry logic"""
        url = f"{self.base_url}/control/rewrite/{operation}"
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                if isinstance(payload, RewriteRule):
                    json_payload = payload.to_dict()
                else:
                    json_payload = payload
                
                response = self.session.post(url, json=json_payload, timeout=self.request_timeout)
                duration_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    logger.adguard_api_call(f"rule_{operation}", True, duration_ms)
                    return True
                else:
                    logger.adguard_api_call(f"rule_{operation}", False, duration_ms)
                    logger.error(f"Rule {operation} failed: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.adguard_api_call(f"rule_{operation}", False)
                logger.error(f"Rule {operation} attempt {attempt + 1} failed: {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        return False
    
    def sync_rules(self, target_rules: Dict[str, RewriteRule], managed_rules: Dict[str, RewriteRule] = None) -> bool:
        """Sync rules to match target state - SAFE approach that only manages app-created rules"""
        logger.sync_start(len(target_rules))
        
        try:
            # Get current rules
            current_rules = self.get_rewrite_rules()
            if not current_rules:
                logger.warning("Failed to get current rules from AdGuardHome")
                return False
            
            logger.info(f"Current rules in AdGuardHome: {len(current_rules)}", 
                       current_rule_count=len(current_rules))
            logger.info(f"Target rules to sync: {len(target_rules)}", 
                       target_rule_count=len(target_rules))
            
            # Debug: Log current and target rule details
            logger.debug("Current rules in AdGuardHome:", current_rules={k: v.answer for k, v in current_rules.items()})
            logger.debug("Target rules to sync:", target_rules={k: v.answer for k, v in target_rules.items()})
            
            # SAFE APPROACH: Only manage rules we previously created
            if managed_rules is not None:
                # Only consider rules we previously managed
                app_managed_domains = set(managed_rules.keys())
                logger.info(f"Previously managed rules: {len(app_managed_domains)}", 
                           managed_rule_count=len(app_managed_domains))
            else:
                # If no managed rules provided, only work with target rules (don't delete anything)
                app_managed_domains = set()
                logger.warning("No managed rules provided - will only add/update, not delete")
            
            # Calculate differences - SAFE approach
            current_domains = set(current_rules.keys())
            target_domains = set(target_rules.keys())
            
            # Rules to add/update (target rules not in current)
            to_add_or_update = target_domains - current_domains
            to_update = current_domains & target_domains
            
            # SAFE: Only delete rules we previously managed that are no longer in target
            to_delete = app_managed_domains - target_domains
            
            # SAFETY CHECK: Prevent accidental deletion of all rules
            if len(to_delete) > len(app_managed_domains) * self.safety_threshold:  # If deleting more than threshold% of managed rules
                logger.error(f"SAFETY CHECK FAILED: Attempting to delete {len(to_delete)} out of {len(app_managed_domains)} managed rules. This seems dangerous!")
                logger.error("Aborting sync to prevent accidental deletion of rules")
                return False
            
            logger.info(f"Rules to add: {len(to_add_or_update)}", 
                       rules_to_add=list(to_add_or_update))
            logger.info(f"Rules to update: {len(to_update)}", 
                       rules_to_update=list(to_update))
            logger.info(f"Rules to delete: {len(to_delete)}", 
                       rules_to_delete=list(to_delete))
            
            rules_created = 0
            rules_updated = 0
            rules_deleted = 0
            
            # Add new rules
            for domain in to_add_or_update:
                rule = target_rules[domain]
                if self.add_rewrite_rule(rule):
                    rules_created += 1
                    logger.rule_created(domain, rule.answer)
                else:
                    logger.error(f"Failed to add rule: {domain}")
            
            # Update existing rules
            for domain in to_update:
                rule = target_rules[domain]
                current_rule = current_rules[domain]
                
                logger.info(f"Checking rule {domain}: current={current_rule.answer}, target={rule.answer}")
                
                if current_rule.answer != rule.answer or current_rule.enabled != rule.enabled:
                    logger.info(f"Rule {domain} needs update: {current_rule.answer} -> {rule.answer}")
                    if self.update_rewrite_rule(rule, current_rules):
                        rules_updated += 1
                        logger.rule_updated(domain, current_rule.answer, rule.answer)
                    else:
                        logger.error(f"Failed to update rule: {domain}")
                else:
                    logger.info(f"Rule {domain} is already correct, skipping update")
            
            # Delete obsolete rules
            for domain in to_delete:
                if self.delete_rewrite_rule(domain, current_rules):
                    rules_deleted += 1
                    logger.rule_deleted(domain)
                else:
                    logger.error(f"Failed to delete rule: {domain}")
            
            # Log results
            total_processed = rules_created + rules_updated + rules_deleted
            logger.info(f"Sync completed: {rules_created} created, {rules_updated} updated, {rules_deleted} deleted", 
                       rules_created=rules_created, rules_updated=rules_updated, rules_deleted=rules_deleted)
            
            if total_processed > 0:
                logger.sync_success(rules_created, rules_updated, rules_deleted)
            else:
                logger.info("All rules are already in sync, no changes needed")
            
            # Consider it successful even if no changes were needed
            return True
            
        except Exception as e:
            logger.sync_error(str(e), len(target_rules))
            return False
