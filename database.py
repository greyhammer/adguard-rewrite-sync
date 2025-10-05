"""
Rule persistence with backup/restore functionality
"""

import os
import json
import shutil
import glob
import threading
import time
from datetime import datetime
from typing import Dict
from models import RewriteRule
from logger import logger


class RuleDatabase:
    """Manages rule persistence with backup/restore functionality"""
    
    def __init__(self, db_file: str, max_backups: int = None):
        self.db_file = db_file
        self.backup_file = f"{db_file}.backup"
        self.max_backups = max_backups or int(os.getenv('DB_MAX_BACKUPS', '5'))
        self.debug_log_chars = int(os.getenv('DB_DEBUG_LOG_CHARS', '500'))
        
        # Single lock for all database operations to prevent deadlocks
        # All methods acquire this lock in the same order
        # Using RLock for timeout support to prevent indefinite blocking
        self._lock = threading.RLock()
        self._lock_timeout = float(os.getenv('DB_LOCK_TIMEOUT', '30.0'))  # Configurable timeout for lock acquisition
        
        # Validate configuration
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate database configuration"""
        if self.max_backups < 1 or self.max_backups > 50:
            raise ValueError(f"DB_MAX_BACKUPS must be between 1 and 50, got {self.max_backups}")
        
        if self._lock_timeout < 1.0 or self._lock_timeout > 300.0:
            raise ValueError(f"DB_LOCK_TIMEOUT must be between 1.0 and 300.0 seconds, got {self._lock_timeout}")
        
        if self.debug_log_chars < 100 or self.debug_log_chars > 2000:
            raise ValueError(f"DB_DEBUG_LOG_CHARS must be between 100 and 2000, got {self.debug_log_chars}")
        
        logger.info("Database configuration validated",
                    max_backups=self.max_backups,
                    lock_timeout=self._lock_timeout,
                    debug_log_chars=self.debug_log_chars)
    
    def _acquire_lock_with_timeout(self):
        """Acquire lock with timeout to prevent indefinite blocking"""
        if not self._lock.acquire(timeout=self._lock_timeout):
            raise RuntimeError(f"Failed to acquire database lock within {self._lock_timeout} seconds")
        return True
    
    def _release_lock(self):
        """Release the database lock"""
        self._lock.release()
    
    def load_managed_rules(self) -> Dict[str, RewriteRule]:
        """Load managed rules with automatic backup restoration on corruption"""
        self._acquire_lock_with_timeout()
        try:
            # Try main file first
            if os.path.exists(self.db_file):
                try:
                    rules = self._load_from_file(self.db_file)
                    # Check if we got any valid rules
                    if rules:
                        logger.info(f"Successfully loaded {len(rules)} rules from main database")
                        return rules
                    else:
                        logger.warning("Main database file exists but contains no valid rules, starting fresh")
                        self._cleanup_corrupted_file(self.db_file)
                        return {}
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Main database corrupted: {e}")
                    self._cleanup_corrupted_file(self.db_file)
                    return self._try_backup_restore()
            
            # Try backup file if main doesn't exist
            if os.path.exists(self.backup_file):
                try:
                    logger.info("Main database not found, trying backup...")
                    rules = self._load_from_file(self.backup_file)
                    if rules:
                        # Restore main file from backup
                        shutil.copy2(self.backup_file, self.db_file)
                        logger.info("Successfully restored main database from backup")
                        return rules
                    else:
                        logger.warning("Backup database exists but contains no valid rules")
                        return {}
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.error(f"Backup database also corrupted: {e}")
                    self._cleanup_corrupted_file(self.backup_file)
            
            logger.info("No valid database found, starting fresh")
            return {}
        finally:
            self._release_lock()
    
    def _cleanup_corrupted_file(self, file_path: str):
        """Clean up a corrupted database file by moving it to a .corrupted backup"""
        try:
            if os.path.exists(file_path):
                corrupted_backup = f"{file_path}.corrupted.{int(time.time())}"
                shutil.move(file_path, corrupted_backup)
                logger.info(f"Moved corrupted file {file_path} to {corrupted_backup}")
        except Exception as e:
            logger.warning(f"Failed to cleanup corrupted file {file_path}: {e}")
    
    def _load_from_file(self, file_path: str) -> Dict[str, RewriteRule]:
        """Load rules from a specific file"""
        logger.info(f"Loading rules from file: {file_path}")
        
        with open(file_path, 'r') as f:
            raw_content = f.read()
            logger.debug(f"Raw file content: {raw_content[:self.debug_log_chars]}...")  # Show first N chars
            
            data = json.loads(raw_content)
            logger.info(f"Parsed JSON data type: {type(data)}")
            
            # Validate that data is a dictionary
            if not isinstance(data, dict):
                logger.error(f"Expected dictionary in database file, got {type(data)}: {data}")
                raise ValueError(f"Invalid database format: expected dict, got {type(data)}")
            
            logger.info(f"Found {len(data)} entries in database")
            rules = {}
            for domain, rule_data in data.items():
                logger.debug(f"Processing domain '{domain}' with data: {rule_data}")
                
                # Validate that rule_data is a dictionary
                if not isinstance(rule_data, dict):
                    logger.warning(f"Skipping invalid rule data at domain '{domain}' - expected dict, got {type(rule_data)}: {rule_data}")
                    continue
                
                # Validate required fields
                if not all(key in rule_data for key in ['domain', 'answer', 'enabled']):
                    logger.error(f"Missing required fields in rule data for domain '{domain}': {rule_data}")
                    continue
                
                rules[domain] = RewriteRule(
                    domain=rule_data['domain'],
                    answer=rule_data['answer'],
                    enabled=rule_data['enabled']
                )
            return rules
    
    def _try_backup_restore(self) -> Dict[str, RewriteRule]:
        """Try to restore from backup files"""
        # Look for timestamped backup files
        backup_pattern = f"{self.db_file}.backup.*"
        backup_files = sorted(glob.glob(backup_pattern), reverse=True)
        
        for backup_file in backup_files:
            try:
                logger.info(f"Attempting to restore from {backup_file}")
                rules = self._load_from_file(backup_file)
                # Restore main file from backup
                shutil.copy2(backup_file, self.db_file)
                logger.info(f"Successfully restored from {backup_file}")
                return rules
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Backup {backup_file} also corrupted: {e}")
                continue
        
        # Try the main backup file
        if os.path.exists(self.backup_file):
            try:
                logger.info("Attempting to restore from main backup file")
                rules = self._load_from_file(self.backup_file)
                shutil.copy2(self.backup_file, self.db_file)
                logger.info("Successfully restored from main backup file")
                return rules
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(f"Main backup file also corrupted: {e}")
        
        logger.warning("No valid backup found, starting fresh")
        return {}
    
    def save_managed_rules(self, rules: Dict[str, RewriteRule]):
        """Save managed rules with automatic backup creation"""
        self._acquire_lock_with_timeout()
        try:
            try:
                # Create backup before saving
                if os.path.exists(self.db_file):
                    self._create_backup()
                
                # Save to main file
                self._save_to_file(rules, self.db_file)
                logger.info(f"Saved {len(rules)} managed rules to database")
            except Exception as e:
                logger.error(f"Failed to save managed rules: {e}")
                raise
        finally:
            self._release_lock()
    
    def _create_backup(self):
        """Create a timestamped backup of the current database"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{self.db_file}.backup.{timestamp}"
            shutil.copy2(self.db_file, backup_name)
            logger.debug(f"Created backup: {backup_name}")
            
            # Also update the main backup file
            shutil.copy2(self.db_file, self.backup_file)
            
            # Clean up old backups
            self._cleanup_old_backups()
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    def _cleanup_old_backups(self):
        """Remove old backup files, keeping only the most recent ones"""
        try:
            backup_pattern = f"{self.db_file}.backup.*"
            backup_files = sorted(glob.glob(backup_pattern), reverse=True)
            
            # Keep only the most recent backups
            for backup_file in backup_files[self.max_backups:]:
                try:
                    os.remove(backup_file)
                    logger.debug(f"Removed old backup: {backup_file}")
                except OSError as e:
                    logger.warning(f"Failed to remove old backup {backup_file}: {e}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    def _save_to_file(self, rules: Dict[str, RewriteRule], file_path: str):
        """Save rules to a specific file"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        data = {}
        for domain, rule in rules.items():
            data[domain] = {
                'domain': rule.domain,
                'answer': rule.answer,
                'enabled': rule.enabled
            }
        
        # Write to temporary file first, then rename (atomic operation)
        temp_file = f"{file_path}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Atomic rename
        shutil.move(temp_file, file_path)
