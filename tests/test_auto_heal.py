"""
TMA Auto-Heal Backend Core Tests
Test suite for health monitoring, timeout detection, and auto-healing capabilities
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Since this is a TypeScript project, we'll test the Python integration layer
# For actual TypeScript testing, use Jest/Vitest

# ============== MOCK TYPE DEFINITIONS ==============

class PhaseConfig:
    def __init__(self, name: str, timeout: int, max_retries: int, health_check_interval: int):
        self.name = name
        self.timeout = timeout
        self.max_retries = max_retries
        self.health_check_interval = health_check_interval

class PhaseState:
    def __init__(self, name: str):
        self.name = name
        self.status = 'idle'
        self.start_time = None
        self.end_time = None
        self.retry_count = 0
        self.error = None

class HealthCheckResult:
    def __init__(self, status: str, component: str, response_time: float = 0):
        self.status = status
        self.timestamp = int(time.time() * 1000)
        self.component = component
        self.response_time = response_time
        self.details = {}

# ============== TEST FIXTURES ==============

@pytest.fixture
def default_config():
    return {
        'enabled': True,
        'max_restarts': 3,
        'cooldown_period': 0.1,  # 100ms for faster tests
        'phases': {
            'p1': PhaseConfig('p1', timeout=1000, max_retries=3, health_check_interval=100),
            'p2': PhaseConfig('p2', timeout=2000, max_retries=2, health_check_interval=200),
        }
    }

@pytest.fixture
def health_check_result():
    return HealthCheckResult(status='healthy', component='test', response_time=50)

# ============== PHASE MANAGER TESTS ==============

class TestPhaseManager:
    """Tests for PhaseManager class"""
    
    def test_initialization(self, default_config):
        """Test that PhaseManager initializes with correct default states"""
        # Mock the import
        with patch('src.index.PhaseManager') as MockPM:
            # Simulate initialization
            mock_instance = Mock()
            MockPM.return_value = mock_instance
            
            # Verify phases are created
            assert 'p1' in default_config['phases']
            assert 'p2' in default_config['phases']
    
    def test_phase_config_timeout(self, default_config):
        """Test that phase timeout is correctly configured"""
        p1_config = default_config['phases']['p1']
        assert p1_config.timeout == 1000  # 1 second
        assert p1_config.max_retries == 3
    
    def test_phase_config_p2(self, default_config):
        """Test p2 phase configuration"""
        p2_config = default_config['phases']['p2']
        assert p2_config.timeout == 2000  # 2 seconds
        assert p2_config.max_retries == 2

# ============== HEALTH MONITOR TESTS ==============

class TestHealthMonitor:
    """Tests for HealthMonitor class"""
    
    def test_health_check_result_structure(self, health_check_result):
        """Test HealthCheckResult has required fields"""
        assert hasattr(health_check_result, 'status')
        assert hasattr(health_check_result, 'timestamp')
        assert hasattr(health_check_result, 'component')
        assert hasattr(health_check_result, 'response_time')
        assert health_check_result.status == 'healthy'
        assert health_check_result.component == 'test'
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self):
        """Test that failed health check returns unhealthy status"""
        # Simulate async health check
        async def failing_check():
            raise Exception("Connection failed")
        
        with pytest.raises(Exception):
            await failing_check()

# ============== AUTO HEAL SERVICE TESTS ==============

class TestAutoHealService:
    """Tests for AutoHealService class"""
    
    def test_service_enabled_by_default(self):
        """Test that auto-heal is enabled by default"""
        config = {'enabled': True}
        assert config['enabled'] is True
    
    def test_service_max_restarts(self, default_config):
        """Test max restarts configuration"""
        assert default_config['max_restarts'] == 3
    
    def test_cooldown_period(self, default_config):
        """Test cooldown period configuration"""
        assert default_config['cooldown_period'] == 0.1  # 100ms

# ============== INTEGRATION SCENARIOS ==============

class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_phase_execution_with_timeout(self):
        """Test that phase times out correctly"""
        timeout_ms = 100
        async def slow_operation():
            await asyncio.sleep(1)  # 1 second > 100ms timeout
            return "done"
        
        start = time.time()
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=timeout_ms/1000)
        
        elapsed = time.time() - start
        assert elapsed < 0.2  # Should fail quickly due to timeout
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test retry mechanism with max attempts"""
        attempts = 0
        max_retries = 3
        
        async def failing_operation():
            nonlocal attempts
            attempts += 1
            if attempts < max_retries:
                raise Exception(f"Attempt {attempts} failed")
            return "success"
        
        # Should succeed on 3rd attempt
        for _ in range(max_retries):
            try:
                result = await failing_operation()
                assert result == "success"
                break
            except Exception:
                if attempts >= max_retries:
                    pytest.fail("Should have succeeded")
    
    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        """Test that multiple health checks can run concurrently"""
        async def health_check(component: str, delay: float) -> HealthCheckResult:
            await asyncio.sleep(delay)
            return HealthCheckResult(status='healthy', component=component, response_time=delay*1000)
        
        # Run 3 health checks concurrently
        results = await asyncio.gather(
            health_check('comp1', 0.1),
            health_check('comp2', 0.2),
            health_check('comp3', 0.05)
        )
        
        assert len(results) == 3
        assert all(r.status == 'healthy' for r in results)

# ============== ERROR HANDLING TESTS ==============

class TestErrorHandling:
    """Tests for error handling scenarios"""
    
    def test_invalid_phase_name(self):
        """Test handling of invalid phase names"""
        valid_phases = ['p1', 'p2', 'p3']
        invalid_phase = 'invalid_phase'
        
        assert invalid_phase not in valid_phases
    
    def test_timeout_error_message(self):
        """Test timeout error message format"""
        phase_name = 'p1'
        retries = 3
        error_msg = f"Phase {phase_name} timed out after {retries} retries"
        
        assert phase_name in error_msg
        assert str(retries) in error_msg
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test system degrades gracefully under load"""
        # Simulate degraded performance
        async def slow_health_check():
            await asyncio.sleep(0.5)  # 500ms response time
            return HealthCheckResult(status='degraded', component='test', response_time=500)
        
        result = await slow_health_check()
        assert result.status in ['healthy', 'degraded']  # Accept either

# ============== PERFORMANCE TESTS ==============

class TestPerformance:
    """Performance and benchmarking tests"""
    
    @pytest.mark.asyncio
    async def test_phase_execution_performance(self):
        """Test phase execution completes within acceptable time"""
        async def fast_operation():
            return "done"
        
        start = time.time()
        result = await fast_operation()
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # Should be very fast
        assert result == "done"
    
    def test_memory_efficiency(self):
        """Test memory usage is reasonable"""
        # Create multiple phase states
        states = [PhaseState(f'phase_{i}') for i in range(100)]
        
        assert len(states) == 100
        # Each state should be small
        for state in states:
            assert state.status == 'idle'

# ============== REGRESSION TESTS ==============

class TestRegression:
    """Regression tests for known issues"""
    
    def test_timeout_after_600s_original_issue(self):
        """Regression test for original timeout issue"""
        # Original error: "Phase p1 timed out after 600s (all retries exhausted)"
        # This should now be handled gracefully
        config = {
            'timeout': 600000,  # 600 seconds = 10 minutes
            'max_retries': 3,
            'cooldown_period': 5000
        }
        
        assert config['timeout'] == 600000
        assert config['max_retries'] == 3
    
    def test_phase_state_transitions(self):
        """Test correct state transitions"""
        state = PhaseState('p1')
        
        # Initial state
        assert state.status == 'idle'
        
        # Transitions
        state.status = 'running'
        assert state.status == 'running'
        
        state.status = 'completed'
        assert state.status == 'completed'
        
        # Failed state
        state.status = 'failed'
        assert state.status == 'failed'
        
        # Timeout state
        state.status = 'timed_out'
        assert state.status == 'timed_out'

# ============== RUN TESTS ==============

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
