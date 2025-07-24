#!/usr/bin/env python3
"""
Comprehensive validation script for Pinfairy Bot optimization
Validates imports, syntax, performance, and functionality
"""

import sys
import os
import time
import asyncio
import importlib
import traceback
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class ValidationResult:
    """Validation result container"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors = []
        self.warnings_list = []
        self.performance_metrics = {}
    
    def add_success(self, test_name: str):
        """Add successful test"""
        self.passed += 1
        print(f"✅ {test_name}")
    
    def add_failure(self, test_name: str, error: str):
        """Add failed test"""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"❌ {test_name}: {error}")
    
    def add_warning(self, test_name: str, warning: str):
        """Add warning"""
        self.warnings += 1
        self.warnings_list.append(f"{test_name}: {warning}")
        print(f"⚠️ {test_name}: {warning}")
    
    def add_performance_metric(self, metric_name: str, value: float):
        """Add performance metric"""
        self.performance_metrics[metric_name] = value
    
    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"⚠️ Warnings: {self.warnings}")
        
        if self.performance_metrics:
            print(f"\n📊 Performance Metrics:")
            for metric, value in self.performance_metrics.items():
                print(f"   {metric}: {value:.3f}s")
        
        if self.errors:
            print(f"\n❌ Errors:")
            for error in self.errors:
                print(f"   {error}")
        
        if self.warnings_list:
            print(f"\n⚠️ Warnings:")
            for warning in self.warnings_list:
                print(f"   {warning}")
        
        print("="*60)
        return self.failed == 0


class PinfairyValidator:
    """Main validation class"""
    
    def __init__(self):
        self.result = ValidationResult()
        self.project_root = project_root
    
    def validate_imports(self) -> bool:
        """Validate all imports work correctly"""
        print("\n🔍 Validating imports...")
        
        # Core modules to test
        modules_to_test = [
            'bot',
            'core',
            'config',
            'constants',
            'exceptions',
            'services.database',
            'services.pinterest',
            'services.config_manager',
            'services.monitoring',
            'handlers.commands',
            'handlers.callbacks',
            'utils.logger'
        ]
        
        for module_name in modules_to_test:
            try:
                start_time = time.time()
                importlib.import_module(module_name)
                import_time = time.time() - start_time
                
                self.result.add_success(f"Import {module_name}")
                self.result.add_performance_metric(f"import_{module_name}", import_time)
                
                if import_time > 1.0:
                    self.result.add_warning(
                        f"Import {module_name}", 
                        f"Slow import time: {import_time:.3f}s"
                    )
                    
            except ImportError as e:
                self.result.add_failure(f"Import {module_name}", str(e))
            except Exception as e:
                self.result.add_failure(f"Import {module_name}", f"Unexpected error: {str(e)}")
        
        return True
    
    def validate_syntax(self) -> bool:
        """Validate Python syntax for all files"""
        print("\n🔍 Validating syntax...")
        
        python_files = []
        for pattern in ['**/*.py']:
            python_files.extend(self.project_root.glob(pattern))
        
        # Exclude test files and __pycache__
        python_files = [
            f for f in python_files 
            if '__pycache__' not in str(f) and 'test_' not in f.name
        ]
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                compile(source, str(py_file), 'exec')
                self.result.add_success(f"Syntax {py_file.name}")
                
            except SyntaxError as e:
                self.result.add_failure(
                    f"Syntax {py_file.name}", 
                    f"Line {e.lineno}: {e.msg}"
                )
            except Exception as e:
                self.result.add_failure(f"Syntax {py_file.name}", str(e))
        
        return True
    
    def validate_database_operations(self) -> bool:
        """Validate database operations"""
        print("\n🔍 Validating database operations...")
        
        try:
            from services.database import DatabaseService
            import tempfile
            
            # Create temporary database
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name
            
            async def test_db_operations():
                try:
                    # Initialize database
                    start_time = time.time()
                    db_service = DatabaseService(db_path)
                    await db_service.initialize()
                    init_time = time.time() - start_time
                    
                    self.result.add_success("Database initialization")
                    self.result.add_performance_metric("db_init", init_time)
                    
                    # Test user operations
                    start_time = time.time()
                    success = await db_service.create_user(12345, "test_user", "Test", "User")
                    create_time = time.time() - start_time
                    
                    if success:
                        self.result.add_success("Database user creation")
                        self.result.add_performance_metric("db_create_user", create_time)
                    else:
                        self.result.add_failure("Database user creation", "Failed to create user")
                    
                    # Test query performance
                    start_time = time.time()
                    profile = await db_service.get_user_profile(12345)
                    query_time = time.time() - start_time
                    
                    if profile:
                        self.result.add_success("Database user query")
                        self.result.add_performance_metric("db_query_user", query_time)
                    else:
                        self.result.add_failure("Database user query", "Failed to retrieve user")
                    
                    # Test connection pool
                    start_time = time.time()
                    tasks = []
                    for i in range(10):
                        task = db_service.execute_query("SELECT 1", fetch_one=True)
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks)
                    pool_time = time.time() - start_time
                    
                    if all(r.data for r in results):
                        self.result.add_success("Database connection pool")
                        self.result.add_performance_metric("db_pool_test", pool_time)
                    else:
                        self.result.add_failure("Database connection pool", "Some queries failed")
                    
                    await db_service.close()
                    
                except Exception as e:
                    self.result.add_failure("Database operations", str(e))
                finally:
                    # Cleanup
                    if os.path.exists(db_path):
                        os.unlink(db_path)
            
            # Run async test
            asyncio.run(test_db_operations())
            
        except Exception as e:
            self.result.add_failure("Database validation setup", str(e))
        
        return True
    
    def validate_pinterest_service(self) -> bool:
        """Validate Pinterest service"""
        print("\n🔍 Validating Pinterest service...")
        
        try:
            from services.pinterest import PinterestService, CacheManager, ConnectionPool
            
            async def test_pinterest_service():
                try:
                    # Test cache manager
                    start_time = time.time()
                    cache_manager = CacheManager()
                    cache_manager.set("test_key", {"data": "test"})
                    cached_data = cache_manager.get("test_key")
                    cache_time = time.time() - start_time
                    
                    if cached_data and cached_data["data"] == "test":
                        self.result.add_success("Pinterest cache manager")
                        self.result.add_performance_metric("pinterest_cache", cache_time)
                    else:
                        self.result.add_failure("Pinterest cache manager", "Cache operation failed")
                    
                    # Test connection pool
                    start_time = time.time()
                    pool = ConnectionPool(max_connections=3)
                    client = await pool.get_client()
                    await pool.return_client(client)
                    await pool.close_all()
                    pool_time = time.time() - start_time
                    
                    self.result.add_success("Pinterest connection pool")
                    self.result.add_performance_metric("pinterest_pool", pool_time)
                    
                    # Test service initialization
                    start_time = time.time()
                    service = PinterestService()
                    await service.initialize()
                    await service.close()
                    service_time = time.time() - start_time
                    
                    self.result.add_success("Pinterest service initialization")
                    self.result.add_performance_metric("pinterest_service_init", service_time)
                    
                except Exception as e:
                    self.result.add_failure("Pinterest service", str(e))
            
            # Run async test
            asyncio.run(test_pinterest_service())
            
        except Exception as e:
            self.result.add_failure("Pinterest service validation setup", str(e))
        
        return True
    
    def validate_error_handling(self) -> bool:
        """Validate error handling system"""
        print("\n🔍 Validating error handling...")
        
        try:
            from exceptions import (
                ErrorHandler, ErrorContext, PinfairyException,
                PinterestAPIException, DatabaseException
            )
            
            # Test error context
            context = ErrorContext(
                user_id=12345,
                username="test_user",
                command="test_command"
            )
            
            if context.user_id == 12345 and context.timestamp is not None:
                self.result.add_success("Error context creation")
            else:
                self.result.add_failure("Error context creation", "Invalid context data")
            
            # Test error handler
            error_handler = ErrorHandler()
            test_exception = PinterestAPIException("Test error", status_code=429)
            
            user_message = error_handler.handle_exception(test_exception, context)
            
            if isinstance(user_message, str) and "❌" in user_message:
                self.result.add_success("Error handler processing")
            else:
                self.result.add_failure("Error handler processing", "Invalid user message")
            
            # Test error statistics
            stats = error_handler.get_error_stats()
            if isinstance(stats, dict) and 'total_errors' in stats:
                self.result.add_success("Error statistics")
            else:
                self.result.add_failure("Error statistics", "Invalid statistics format")
            
        except Exception as e:
            self.result.add_failure("Error handling validation", str(e))
        
        return True
    
    def validate_performance(self) -> bool:
        """Validate overall performance"""
        print("\n🔍 Validating performance...")
        
        # Check if any operations are too slow
        slow_operations = []
        for metric, value in self.result.performance_metrics.items():
            if value > 2.0:  # 2 second threshold
                slow_operations.append(f"{metric}: {value:.3f}s")
        
        if slow_operations:
            self.result.add_warning(
                "Performance", 
                f"Slow operations detected: {', '.join(slow_operations)}"
            )
        else:
            self.result.add_success("Performance metrics within acceptable range")
        
        return True
    
    def run_validation(self) -> bool:
        """Run complete validation"""
        print("🚀 Starting Pinfairy Bot Optimization Validation")
        print("="*60)
        
        try:
            # Run all validation steps
            self.validate_imports()
            self.validate_syntax()
            self.validate_database_operations()
            self.validate_pinterest_service()
            self.validate_error_handling()
            self.validate_performance()
            
            # Print summary
            success = self.result.print_summary()
            
            if success:
                print("\n🎉 All validations passed! The optimization is successful.")
            else:
                print("\n⚠️ Some validations failed. Please review the errors above.")
            
            return success
            
        except Exception as e:
            print(f"\n💥 Validation failed with unexpected error: {str(e)}")
            traceback.print_exc()
            return False


def main():
    """Main validation entry point"""
    validator = PinfairyValidator()
    success = validator.run_validation()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
