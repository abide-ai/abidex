"""
HTTP sink for sending telemetry events to remote endpoints.
"""

import json
import time
from typing import Dict, List, Optional, Any
from threading import Lock, Thread
from queue import Queue, Empty
from urllib.parse import urljoin
import requests

from ..client import Event, TelemetrySink
from ..utils.redaction import redact_sensitive_data


class HTTPSink:
    """
    Sink that sends events to an HTTP endpoint.
    """
    
    def __init__(
        self,
        endpoint_url: str,
        headers: Optional[Dict[str, str]] = None,
        batch_size: int = 10,
        batch_timeout: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        redact_sensitive: bool = True,
        auth_token: Optional[str] = None,
        verify_ssl: bool = True
    ):
        self.endpoint_url = endpoint_url
        self.headers = headers or {}
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.redact_sensitive = redact_sensitive
        self.verify_ssl = verify_ssl
        
        # Set up authentication
        if auth_token:
            self.headers['Authorization'] = f'Bearer {auth_token}'
        
        # Set content type
        if 'Content-Type' not in self.headers:
            self.headers['Content-Type'] = 'application/json'
        
        # Batching setup
        self._queue: Queue[Event] = Queue()
        self._batch: List[Event] = []
        self._last_batch_time = time.time()
        self._lock = Lock()
        self._running = True
        
        # Start background thread for batching
        self._thread = Thread(target=self._batch_worker, daemon=True)
        self._thread.start()
    
    def _batch_worker(self) -> None:
        """Background worker for batching and sending events."""
        while self._running:
            try:
                # Try to get an event with timeout
                try:
                    event = self._queue.get(timeout=1.0)
                    self._add_to_batch(event)
                except Empty:
                    pass
                
                # Check if we should send the batch
                with self._lock:
                    should_send = (
                        len(self._batch) >= self.batch_size or
                        (self._batch and time.time() - self._last_batch_time >= self.batch_timeout)
                    )
                
                if should_send:
                    self._send_batch()
                    
            except Exception as e:
                print(f"Error in HTTP sink batch worker: {e}")
    
    def _add_to_batch(self, event: Event) -> None:
        """Add an event to the current batch."""
        with self._lock:
            self._batch.append(event)
            if len(self._batch) == 1:  # First event in batch
                self._last_batch_time = time.time()
    
    def _send_batch(self) -> None:
        """Send the current batch of events."""
        with self._lock:
            if not self._batch:
                return
            
            batch_to_send = self._batch.copy()
            self._batch.clear()
            self._last_batch_time = time.time()
        
        self._send_events(batch_to_send)
    
    def _send_events(self, events: List[Event]) -> None:
        """Send a list of events to the HTTP endpoint."""
        if not events:
            return
        
        # Convert events to dict format
        event_dicts = []
        for event in events:
            event_dict = event.to_dict()
            
            # Redact sensitive data if enabled
            if self.redact_sensitive:
                event_dict = redact_sensitive_data(event_dict)
            
            event_dicts.append(event_dict)
        
        # Prepare payload
        payload = {
            'events': event_dicts,
            'timestamp': time.time(),
            'count': len(event_dicts)
        }
        
        # Send with retries
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    self.endpoint_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                
                if response.status_code == 200:
                    break  # Success
                elif response.status_code >= 400:
                    print(f"HTTP sink error {response.status_code}: {response.text}")
                    if response.status_code < 500:
                        break  # Don't retry client errors
                
            except requests.exceptions.RequestException as e:
                print(f"HTTP sink request error (attempt {attempt + 1}): {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < self.max_retries:
                time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
    
    def send(self, event: Event) -> None:
        """Send an event (adds to batch queue)."""
        if not self._running or not event.sampled:
            return
        
        try:
            self._queue.put_nowait(event)
        except Exception as e:
            print(f"Error queuing event in HTTP sink: {e}")
    
    def flush(self) -> None:
        """Flush any pending events."""
        # Process any remaining events in queue
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                self._add_to_batch(event)
            except Empty:
                break
        
        # Send current batch
        self._send_batch()
    
    def close(self) -> None:
        """Close the sink and stop background thread."""
        self._running = False
        
        # Flush remaining events
        self.flush()
        
        # Wait for thread to finish
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)


class StreamingHTTPSink(HTTPSink):
    """
    HTTP sink that sends events immediately without batching.
    """
    
    def __init__(self, endpoint_url: str, **kwargs):
        # Disable batching
        kwargs['batch_size'] = 1
        kwargs['batch_timeout'] = 0.0
        super().__init__(endpoint_url, **kwargs)
    
    def send(self, event: Event) -> None:
        """Send an event immediately."""
        self._send_events([event])


class WebhookSink(HTTPSink):
    """
    Specialized HTTP sink for webhook endpoints.
    """
    
    def __init__(
        self,
        webhook_url: str,
        secret: Optional[str] = None,
        custom_payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.secret = secret
        self.custom_payload = custom_payload or {}
        
        # Set up webhook-specific headers
        headers = kwargs.get('headers', {})
        if secret:
            headers['X-Webhook-Secret'] = secret
        
        super().__init__(webhook_url, headers=headers, **kwargs)
    
    def _send_events(self, events: List[Event]) -> None:
        """Send events with webhook-specific formatting."""
        if not events:
            return
        
        # Convert events
        event_dicts = []
        for event in events:
            event_dict = event.to_dict()
            
            if self.redact_sensitive:
                event_dict = redact_sensitive_data(event_dict)
            
            event_dicts.append(event_dict)
        
        # Prepare webhook payload
        payload = {
            **self.custom_payload,
            'events': event_dicts,
            'timestamp': time.time(),
            'count': len(event_dicts),
            'webhook_version': '1.0'
        }
        
        # Send with retries
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    self.endpoint_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                
                if response.status_code in (200, 201, 202):
                    break
                elif response.status_code >= 400:
                    print(f"Webhook error {response.status_code}: {response.text}")
                    if response.status_code < 500:
                        break
                
            except requests.exceptions.RequestException as e:
                print(f"Webhook request error (attempt {attempt + 1}): {e}")
            
            if attempt < self.max_retries:
                time.sleep(self.retry_delay * (2 ** attempt))
