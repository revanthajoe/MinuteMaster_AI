import pytest
import requests
from time import sleep
import subprocess
import os
import signal

class TestServer:
    @classmethod
    def setup_class(cls):
        # Start the server process
        cls.server_process = subprocess.Popen(['python', 'app.py'])
        sleep(2)  # Wait for server to start
        
    @classmethod
    def teardown_class(cls):
        # Shutdown the server
        cls.server_process.terminate()
        cls.server_process.wait()

    def test_server_running(self):
        try:
            response = requests.get('http://localhost:5000')
            assert response.status_code in [200, 404]  # Server responds
        except requests.ConnectionError:
            pytest.fail("Server is not running")

    def test_transcribe_endpoint(self):
        url = 'http://localhost:5000/transcribe'
        try:
            # Test with empty data first
            response = requests.post(url, files={})
            assert response.status_code == 400  # Should reject empty request
            assert "No audio file provided" in response.json()["error"]
        except requests.ConnectionError:
            pytest.fail("Cannot connect to /transcribe endpoint")

    def test_server_process_running(self):
        assert self.server_process.poll() is None, "Server process has terminated"