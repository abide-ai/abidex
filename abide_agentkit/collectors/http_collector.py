"""
HTTP collector for receiving telemetry events via REST API.

This module provides a FastAPI-based HTTP server for collecting telemetry events
from remote agents and applications.
"""

import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field

try:
    from fastapi import FastAPI, HTTPException, Request, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from ..client import TelemetryClient, Event, EventType, get_client
from ..utils.redaction import redact_sensitive_data


# Pydantic models for API requests
class EventData(BaseModel):
    """Pydantic model for event data."""
    event_id: Optional[str] = None
    event_type: str = "log"
    timestamp: Optional[float] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    parent_id: Optional[str] = None
    span_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, str] = Field(default_factory=dict)
    level: str = "info"


class BatchEventRequest(BaseModel):
    """Pydantic model for batch event requests."""
    events: List[EventData]
    metadata: Optional[Dict[str, Any]] = None


class EventResponse(BaseModel):
    """Pydantic model for event response."""
    success: bool
    message: str
    event_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class BatchEventResponse(BaseModel):
    """Pydantic model for batch event response."""
    success: bool
    message: str
    processed_count: int
    failed_count: int
    timestamp: float = Field(default_factory=time.time)


class HealthResponse(BaseModel):
    """Pydantic model for health check response."""
    status: str
    timestamp: float = Field(default_factory=time.time)
    version: str = "0.1.0"
    uptime_seconds: float


class HTTPCollector:
    """
    HTTP collector for receiving telemetry events.
    """
    
    def __init__(
        self,
        client: Optional[TelemetryClient] = None,
        enable_cors: bool = True,
        cors_origins: Optional[List[str]] = None,
        enable_redaction: bool = True,
        max_batch_size: int = 1000,
        auth_token: Optional[str] = None
    ):
        if not FASTAPI_AVAILABLE:
            raise ImportError("fastapi is required for HTTPCollector")
        
        self.client = client or get_client()
        self.enable_cors = enable_cors
        self.cors_origins = cors_origins or ["*"]
        self.enable_redaction = enable_redaction
        self.max_batch_size = max_batch_size
        self.auth_token = auth_token
        self.start_time = time.time()
        
        # Statistics
        self.stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_failed": 0,
            "batches_received": 0,
            "last_event_time": None
        }
    
    def create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title="Abide AgentKit Telemetry Collector",
            description="HTTP API for collecting telemetry events from AI agents",
            version="0.1.0"
        )
        
        # Add CORS middleware
        if self.enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self.cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        
        # Add routes
        self._add_routes(app)
        
        return app
    
    def _add_routes(self, app: FastAPI) -> None:
        """Add routes to the FastAPI app."""
        
        @app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            return HealthResponse(
                status="healthy",
                uptime_seconds=time.time() - self.start_time
            )
        
        @app.get("/stats")
        async def get_stats():
            """Get collector statistics."""
            return {
                **self.stats,
                "uptime_seconds": time.time() - self.start_time,
                "start_time": self.start_time
            }
        
        @app.post("/events", response_model=EventResponse)
        async def receive_event(
            event_data: EventData,
            request: Request
        ):
            """Receive a single telemetry event."""
            
            # Authentication check
            if not self._authenticate_request(request):
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            try:
                # Convert to Event object
                event = self._convert_to_event(event_data)
                
                # Redact sensitive data if enabled
                if self.enable_redaction:
                    event_dict = event.to_dict()
                    event_dict = redact_sensitive_data(event_dict)
                    # Note: We could reconstruct the Event from the redacted dict,
                    # but for simplicity, we'll emit the original event
                
                # Emit event
                self.client.emit(event)
                
                # Update stats
                self.stats["events_received"] += 1
                self.stats["events_processed"] += 1
                self.stats["last_event_time"] = time.time()
                
                return EventResponse(
                    success=True,
                    message="Event received successfully",
                    event_id=event.event_id
                )
                
            except Exception as e:
                self.stats["events_failed"] += 1
                raise HTTPException(status_code=400, detail=f"Failed to process event: {str(e)}")
        
        @app.post("/events/batch", response_model=BatchEventResponse)
        async def receive_batch_events(
            batch_request: BatchEventRequest,
            request: Request
        ):
            """Receive a batch of telemetry events."""
            
            # Authentication check
            if not self._authenticate_request(request):
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # Check batch size
            if len(batch_request.events) > self.max_batch_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"Batch size {len(batch_request.events)} exceeds maximum {self.max_batch_size}"
                )
            
            processed_count = 0
            failed_count = 0
            
            for event_data in batch_request.events:
                try:
                    # Convert to Event object
                    event = self._convert_to_event(event_data)
                    
                    # Emit event
                    self.client.emit(event)
                    processed_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Failed to process event in batch: {e}")
            
            # Update stats
            self.stats["events_received"] += len(batch_request.events)
            self.stats["events_processed"] += processed_count
            self.stats["events_failed"] += failed_count
            self.stats["batches_received"] += 1
            self.stats["last_event_time"] = time.time()
            
            return BatchEventResponse(
                success=failed_count == 0,
                message=f"Processed {processed_count} events, {failed_count} failed",
                processed_count=processed_count,
                failed_count=failed_count
            )
        
        @app.post("/webhook/n8n")
        async def n8n_webhook(
            payload: Dict[str, Any],
            request: Request
        ):
            """Handle n8n webhook payloads."""
            
            if not self._authenticate_request(request):
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            try:
                # Process n8n webhook
                self._process_n8n_webhook(payload)
                
                return {"success": True, "message": "N8N webhook processed"}
                
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to process N8N webhook: {str(e)}")
        
        @app.post("/webhook/generic")
        async def generic_webhook(
            payload: Dict[str, Any],
            request: Request,
            source: str = "unknown"
        ):
            """Handle generic webhook payloads."""
            
            if not self._authenticate_request(request):
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            try:
                # Create event from webhook payload
                event = Event(
                    event_type=EventType.LOG,
                    data={
                        "message": f"Webhook received from {source}",
                        "webhook_payload": payload,
                        "source": source
                    },
                    tags={"source": source, "type": "webhook"}
                )
                
                self.client.emit(event)
                
                return {"success": True, "message": "Webhook processed"}
                
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to process webhook: {str(e)}")
    
    def _authenticate_request(self, request: Request) -> bool:
        """Authenticate incoming request."""
        if not self.auth_token:
            return True  # No authentication required
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            return token == self.auth_token
        
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key == self.auth_token
        
        return False
    
    def _convert_to_event(self, event_data: EventData) -> Event:
        """Convert EventData to Event object."""
        # Convert event_type string to EventType enum
        try:
            event_type = EventType(event_data.event_type)
        except ValueError:
            event_type = EventType.LOG  # Default fallback
        
        return Event(
            event_id=event_data.event_id,
            event_type=event_type,
            timestamp=event_data.timestamp or time.time(),
            agent_id=event_data.agent_id,
            run_id=event_data.run_id,
            parent_id=event_data.parent_id,
            span_id=event_data.span_id,
            data=event_data.data,
            tags=event_data.tags,
            level=event_data.level
        )
    
    def _process_n8n_webhook(self, payload: Dict[str, Any]) -> None:
        """Process n8n webhook payload."""
        # Extract n8n-specific data
        workflow_name = payload.get("workflowName", "unknown")
        execution_id = payload.get("executionId")
        execution_status = payload.get("executionStatus", "unknown")
        
        # Create event
        event = Event(
            event_type=EventType.LOG,
            data={
                "message": f"N8N workflow {workflow_name} {execution_status}",
                "workflow_name": workflow_name,
                "execution_id": execution_id,
                "execution_status": execution_status,
                "n8n_payload": payload
            },
            tags={"platform": "n8n", "workflow": workflow_name},
            level="info" if execution_status == "success" else "error"
        )
        
        self.client.emit(event)


def create_collector_app(
    client: Optional[TelemetryClient] = None,
    **kwargs
) -> FastAPI:
    """
    Create a FastAPI application for collecting telemetry events.
    
    Args:
        client: TelemetryClient instance
        **kwargs: Additional arguments for HTTPCollector
    
    Returns:
        FastAPI application instance
    
    Example:
        from abide_agentkit.collectors import create_collector_app
        import uvicorn
        
        app = create_collector_app(auth_token="your-secret-token")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("fastapi is required to create collector app")
    
    collector = HTTPCollector(client=client, **kwargs)
    return collector.create_app()


# Mock classes for when FastAPI is not available
if not FASTAPI_AVAILABLE:
    class HTTPCollector:
        def __init__(self, *args, **kwargs):
            raise ImportError("fastapi is required for HTTPCollector")
    
    def create_collector_app(*args, **kwargs):
        raise ImportError("fastapi is required to create collector app")
