"""
Adapter for integrating with n8n workflow automation platform.
"""

import json
import time
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager
from datetime import datetime

from ..client import TelemetryClient, get_client, Event, EventType
from ..spans import AgentRun, ToolCall
from ..utils.id_utils import generate_run_id


class N8NAdapter:
    """
    Adapter for tracking n8n workflow executions and node operations.
    """
    
    def __init__(self, client: Optional[TelemetryClient] = None):
        self.client = client or get_client()
        self._active_workflows: Dict[str, str] = {}  # workflow_id -> run_id mapping
    
    @contextmanager
    def track_workflow_execution(
        self,
        workflow_name: str,
        workflow_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        trigger_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracking an n8n workflow execution.
        
        Args:
            workflow_name: Name of the workflow
            workflow_id: ID of the workflow in n8n
            execution_id: Execution ID from n8n
            trigger_data: Data that triggered the workflow
            metadata: Additional metadata about the workflow
        
        Yields:
            WorkflowExecutionContext for tracking the execution
        
        Example:
            adapter = N8NAdapter()
            with adapter.track_workflow_execution("customer_onboarding", trigger_data=webhook_data) as workflow:
                workflow.set_input(webhook_data)
                # Execute workflow nodes...
                workflow.set_output(result)
        """
        run_id = generate_run_id("n8n_workflow")
        
        tags = {"platform": "n8n", "workflow": workflow_name}
        if workflow_id:
            tags["workflow_id"] = workflow_id
        
        data = {
            "workflow_name": workflow_name,
            "platform": "n8n",
            "execution_type": "workflow",
            **(metadata or {})
        }
        
        if workflow_id:
            data["workflow_id"] = workflow_id
        if execution_id:
            data["execution_id"] = execution_id
        if trigger_data:
            data["trigger_data"] = trigger_data
        
        with AgentRun(
            name=f"n8n_workflow_{workflow_name}",
            client=self.client,
            tags=tags,
            data=data
        ) as run:
            context = WorkflowExecutionContext(run, workflow_name, self.client)
            
            if workflow_id:
                self._active_workflows[workflow_id] = run.run_id
            
            try:
                yield context
            finally:
                if workflow_id and workflow_id in self._active_workflows:
                    del self._active_workflows[workflow_id]
    
    @contextmanager
    def track_node_execution(
        self,
        node_name: str,
        node_type: str,
        workflow_id: Optional[str] = None,
        node_parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracking individual n8n node execution.
        
        Args:
            node_name: Name of the node
            node_type: Type of the node (e.g., 'HTTP Request', 'Code', 'Webhook')
            workflow_id: ID of the parent workflow
            node_parameters: Parameters configured for the node
            metadata: Additional node metadata
        
        Yields:
            ToolCallContext for tracking the node execution
        """
        run_id = self._active_workflows.get(workflow_id) if workflow_id else None
        
        tags = {"platform": "n8n", "node_type": node_type}
        if workflow_id:
            tags["workflow_id"] = workflow_id
        
        data = {
            "node_name": node_name,
            "node_type": node_type,
            "platform": "n8n",
            **(metadata or {})
        }
        
        if workflow_id:
            data["workflow_id"] = workflow_id
        if node_parameters:
            data["node_parameters"] = node_parameters
        
        with ToolCall(
            tool_name=f"n8n_{node_type}_{node_name}",
            client=self.client,
            run_id=run_id,
            tags=tags,
            data=data
        ) as tool:
            yield NodeExecutionContext(tool, node_name, node_type)
    
    def track_webhook_trigger(
        self,
        workflow_name: str,
        webhook_data: Dict[str, Any],
        workflow_id: Optional[str] = None,
        webhook_url: Optional[str] = None
    ) -> None:
        """
        Track a webhook trigger event.
        
        Args:
            workflow_name: Name of the triggered workflow
            webhook_data: Data received from the webhook
            workflow_id: ID of the workflow
            webhook_url: URL of the webhook endpoint
        """
        run_id = self._active_workflows.get(workflow_id) if workflow_id else None
        
        event = Event(
            event_type=EventType.LOG,
            run_id=run_id,
            data={
                "message": f"Webhook triggered workflow: {workflow_name}",
                "workflow_name": workflow_name,
                "trigger_type": "webhook",
                "webhook_data": webhook_data,
                "platform": "n8n"
            },
            tags={"platform": "n8n", "event": "webhook_trigger"},
            level="info"
        )
        
        if workflow_id:
            event.tags["workflow_id"] = workflow_id
        if webhook_url:
            event.data["webhook_url"] = webhook_url
        
        self.client.emit(event)
    
    def track_schedule_trigger(
        self,
        workflow_name: str,
        schedule_config: Dict[str, Any],
        workflow_id: Optional[str] = None
    ) -> None:
        """
        Track a scheduled trigger event.
        
        Args:
            workflow_name: Name of the triggered workflow
            schedule_config: Schedule configuration
            workflow_id: ID of the workflow
        """
        run_id = self._active_workflows.get(workflow_id) if workflow_id else None
        
        event = Event(
            event_type=EventType.LOG,
            run_id=run_id,
            data={
                "message": f"Schedule triggered workflow: {workflow_name}",
                "workflow_name": workflow_name,
                "trigger_type": "schedule",
                "schedule_config": schedule_config,
                "platform": "n8n"
            },
            tags={"platform": "n8n", "event": "schedule_trigger"},
            level="info"
        )
        
        if workflow_id:
            event.tags["workflow_id"] = workflow_id
        
        self.client.emit(event)
    
    def track_error(
        self,
        error_message: str,
        node_name: Optional[str] = None,
        workflow_id: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track an error in n8n workflow execution.
        
        Args:
            error_message: Error message
            node_name: Name of the node where error occurred
            workflow_id: ID of the workflow
            error_details: Additional error details
        """
        run_id = self._active_workflows.get(workflow_id) if workflow_id else None
        
        event_data = {
            "message": f"n8n error: {error_message}",
            "error_message": error_message,
            "platform": "n8n"
        }
        
        if node_name:
            event_data["node_name"] = node_name
        if workflow_id:
            event_data["workflow_id"] = workflow_id
        if error_details:
            event_data["error_details"] = error_details
        
        event = Event(
            event_type=EventType.ERROR,
            run_id=run_id,
            data=event_data,
            tags={"platform": "n8n", "event": "error"},
            level="error"
        )
        
        self.client.emit(event)


class WorkflowExecutionContext:
    """Context for tracking an n8n workflow execution."""
    
    def __init__(self, agent_run_context, workflow_name: str, client: TelemetryClient):
        self.run = agent_run_context
        self.workflow_name = workflow_name
        self.client = client
        self._nodes_executed = 0
        self._nodes_failed = 0
        self._execution_path: List[str] = []
    
    def set_input(self, inputs: Dict[str, Any]) -> None:
        """Set the input data for the workflow."""
        self.run.add_data("inputs", inputs)
    
    def set_output(self, outputs: Any) -> None:
        """Set the output data for the workflow."""
        self.run.add_data("outputs", outputs)
        self.run.add_data("execution_stats", {
            "nodes_executed": self._nodes_executed,
            "nodes_failed": self._nodes_failed,
            "execution_path": self._execution_path
        })
    
    def log_node_start(self, node_name: str, node_type: str) -> None:
        """Log when a node starts executing."""
        self._execution_path.append(node_name)
        
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data={
                "message": f"Node {node_name} started",
                "node_name": node_name,
                "node_type": node_type,
                "workflow_name": self.workflow_name,
                "execution_order": len(self._execution_path)
            },
            tags={"platform": "n8n", "event": "node_start"}
        )
        self.client.emit(event)
    
    def log_node_success(self, node_name: str, node_type: str, output_data: Optional[Any] = None) -> None:
        """Log when a node completes successfully."""
        self._nodes_executed += 1
        
        event_data = {
            "message": f"Node {node_name} completed successfully",
            "node_name": node_name,
            "node_type": node_type,
            "workflow_name": self.workflow_name,
            "success": True
        }
        
        if output_data is not None:
            # Truncate large outputs
            output_str = str(output_data)
            if len(output_str) > 1000:
                event_data["output_preview"] = output_str[:1000] + "..."
                event_data["output_size"] = len(output_str)
            else:
                event_data["output_data"] = output_data
        
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data=event_data,
            tags={"platform": "n8n", "event": "node_success"}
        )
        self.client.emit(event)
    
    def log_node_error(self, node_name: str, node_type: str, error: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """Log when a node fails."""
        self._nodes_failed += 1
        
        event_data = {
            "message": f"Node {node_name} failed",
            "node_name": node_name,
            "node_type": node_type,
            "workflow_name": self.workflow_name,
            "error": error,
            "success": False
        }
        
        if error_details:
            event_data["error_details"] = error_details
        
        event = Event(
            event_type=EventType.ERROR,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data=event_data,
            tags={"platform": "n8n", "event": "node_error"},
            level="error"
        )
        self.client.emit(event)
    
    def log_condition_branch(self, condition_node: str, branch_taken: str, condition_result: Any) -> None:
        """Log when a conditional node branches."""
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data={
                "message": f"Condition {condition_node} took branch: {branch_taken}",
                "condition_node": condition_node,
                "branch_taken": branch_taken,
                "condition_result": condition_result,
                "workflow_name": self.workflow_name
            },
            tags={"platform": "n8n", "event": "condition_branch"}
        )
        self.client.emit(event)
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the workflow execution."""
        self.run.add_data(key, value)


class NodeExecutionContext:
    """Context for tracking individual n8n node execution."""
    
    def __init__(self, tool_call_context, node_name: str, node_type: str):
        self.tool = tool_call_context
        self.node_name = node_name
        self.node_type = node_type
    
    def set_input(self, input_data: Any) -> None:
        """Set the input data for the node."""
        self.tool.set_input(input_data=input_data)
    
    def set_output(self, output_data: Any, item_count: Optional[int] = None) -> None:
        """Set the output data for the node."""
        output = {"data": output_data}
        if item_count is not None:
            output["item_count"] = item_count
        self.tool.set_output(output)
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set the node parameters."""
        self.tool.add_data("parameters", parameters)
    
    def log_http_request(self, method: str, url: str, status_code: Optional[int] = None, response_time: Optional[float] = None) -> None:
        """Log HTTP request details (for HTTP Request nodes)."""
        http_data = {
            "method": method,
            "url": url
        }
        
        if status_code is not None:
            http_data["status_code"] = status_code
        if response_time is not None:
            http_data["response_time_ms"] = response_time * 1000
        
        self.tool.add_data("http_request", http_data)
    
    def log_database_operation(self, operation: str, table: Optional[str] = None, rows_affected: Optional[int] = None) -> None:
        """Log database operation details."""
        db_data = {"operation": operation}
        
        if table:
            db_data["table"] = table
        if rows_affected is not None:
            db_data["rows_affected"] = rows_affected
        
        self.tool.add_data("database_operation", db_data)


class N8NWebhookHandler:
    """Handler for processing n8n webhook payloads."""
    
    def __init__(self, adapter: Optional[N8NAdapter] = None):
        self.adapter = adapter or N8NAdapter()
    
    def handle_execution_webhook(self, webhook_payload: Dict[str, Any]) -> None:
        """
        Handle n8n execution webhook payload.
        
        Args:
            webhook_payload: Payload from n8n execution webhook
        """
        execution_id = webhook_payload.get("executionId")
        workflow_id = webhook_payload.get("workflowId")
        workflow_name = webhook_payload.get("workflowName", "unknown")
        execution_status = webhook_payload.get("executionStatus")
        
        if execution_status == "success":
            self._handle_successful_execution(webhook_payload)
        elif execution_status == "error":
            self._handle_failed_execution(webhook_payload)
        elif execution_status == "running":
            self._handle_running_execution(webhook_payload)
    
    def _handle_successful_execution(self, payload: Dict[str, Any]) -> None:
        """Handle successful execution webhook."""
        workflow_name = payload.get("workflowName", "unknown")
        execution_id = payload.get("executionId")
        
        with self.adapter.track_workflow_execution(
            workflow_name=workflow_name,
            execution_id=execution_id,
            metadata={"webhook_payload": payload}
        ) as workflow:
            workflow.set_output(payload.get("data", {}))
    
    def _handle_failed_execution(self, payload: Dict[str, Any]) -> None:
        """Handle failed execution webhook."""
        workflow_name = payload.get("workflowName", "unknown")
        error_message = payload.get("errorMessage", "Unknown error")
        
        self.adapter.track_error(
            error_message=error_message,
            workflow_id=payload.get("workflowId"),
            error_details=payload
        )
