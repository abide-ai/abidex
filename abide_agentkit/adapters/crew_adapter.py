"""
Adapter for integrating with CrewAI framework.
"""

import time
from typing import Any, Dict, List, Optional, Callable
from contextlib import contextmanager

from ..client import TelemetryClient, get_client, Event, EventType
from ..spans import AgentRun, ToolCall
from ..utils.id_utils import generate_run_id


class CrewAdapter:
    """
    Adapter for tracking CrewAI crew executions, agent tasks, and tool usage.
    """
    
    def __init__(self, client: Optional[TelemetryClient] = None):
        self.client = client or get_client()
        self._active_runs: Dict[str, str] = {}  # crew_id -> run_id mapping
    
    @contextmanager
    def track_crew_execution(
        self,
        crew_name: str,
        agents: Optional[List[str]] = None,
        tasks: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracking a CrewAI crew execution.
        
        Args:
            crew_name: Name of the crew being executed
            agents: List of agent names in the crew
            tasks: List of task descriptions
            metadata: Additional metadata about the crew
        
        Yields:
            CrewExecutionContext for tracking the crew execution
        
        Example:
            adapter = CrewAdapter()
            with adapter.track_crew_execution("research_crew", agents=["researcher", "writer"]) as crew:
                crew.set_input({"topic": "AI trends"})
                result = crew.kickoff()
                crew.set_output(result)
        """
        run_id = generate_run_id("crew")
        
        with AgentRun(
            name=f"crew_{crew_name}",
            client=self.client,
            data={
                "crew_name": crew_name,
                "agents": agents or [],
                "tasks": tasks or [],
                "framework": "crewai",
                **(metadata or {})
            },
            tags={"framework": "crewai", "crew": crew_name}
        ) as run:
            context = CrewExecutionContext(run, crew_name, self.client)
            self._active_runs[crew_name] = run.run_id
            
            try:
                yield context
            finally:
                if crew_name in self._active_runs:
                    del self._active_runs[crew_name]
    
    def track_agent_task(
        self,
        agent_name: str,
        task_description: str,
        crew_name: Optional[str] = None,
        expected_output: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track an individual agent task execution.
        
        Args:
            agent_name: Name of the agent executing the task
            task_description: Description of the task
            crew_name: Name of the parent crew (if applicable)
            expected_output: Expected output description
            metadata: Additional task metadata
        
        Returns:
            AgentTaskContext for tracking the task
        """
        run_id = self._active_runs.get(crew_name) if crew_name else None
        
        return AgentTaskContext(
            agent_name=agent_name,
            task_description=task_description,
            client=self.client,
            run_id=run_id,
            crew_name=crew_name,
            expected_output=expected_output,
            metadata=metadata
        )
    
    @contextmanager
    def track_tool_usage(
        self,
        tool_name: str,
        agent_name: Optional[str] = None,
        crew_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracking tool usage within CrewAI.
        
        Args:
            tool_name: Name of the tool being used
            agent_name: Name of the agent using the tool
            crew_name: Name of the parent crew
            metadata: Additional tool metadata
        
        Yields:
            ToolCallContext for tracking the tool usage
        """
        run_id = self._active_runs.get(crew_name) if crew_name else None
        
        tags = {"framework": "crewai"}
        if agent_name:
            tags["agent"] = agent_name
        if crew_name:
            tags["crew"] = crew_name
        
        data = {
            "tool_name": tool_name,
            "framework": "crewai",
            **(metadata or {})
        }
        
        if agent_name:
            data["agent_name"] = agent_name
        if crew_name:
            data["crew_name"] = crew_name
        
        with ToolCall(
            tool_name=tool_name,
            client=self.client,
            run_id=run_id,
            tags=tags,
            data=data
        ) as tool:
            yield tool


class CrewExecutionContext:
    """Context for tracking a CrewAI crew execution."""
    
    def __init__(self, agent_run_context, crew_name: str, client: TelemetryClient):
        self.run = agent_run_context
        self.crew_name = crew_name
        self.client = client
        self._agents_started: Dict[str, float] = {}
        self._tasks_completed = 0
    
    def set_input(self, inputs: Dict[str, Any]) -> None:
        """Set the input data for the crew execution."""
        self.run.add_data("inputs", inputs)
    
    def set_output(self, outputs: Any) -> None:
        """Set the output data for the crew execution."""
        self.run.add_data("outputs", outputs)
    
    def log_agent_start(self, agent_name: str) -> None:
        """Log when an agent starts working."""
        self._agents_started[agent_name] = time.time()
        
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data={
                "message": f"Agent {agent_name} started",
                "agent_name": agent_name,
                "crew_name": self.crew_name
            },
            tags={"framework": "crewai", "event": "agent_start"}
        )
        self.client.emit(event)
    
    def log_agent_complete(self, agent_name: str, result: Optional[Any] = None) -> None:
        """Log when an agent completes its work."""
        start_time = self._agents_started.get(agent_name)
        duration = time.time() - start_time if start_time else None
        
        event_data = {
            "message": f"Agent {agent_name} completed",
            "agent_name": agent_name,
            "crew_name": self.crew_name
        }
        
        if duration:
            event_data["duration_seconds"] = duration
        
        if result is not None:
            event_data["result"] = str(result)[:1000]  # Truncate long results
        
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data=event_data,
            tags={"framework": "crewai", "event": "agent_complete"}
        )
        self.client.emit(event)
    
    def log_task_complete(self, task_description: str, agent_name: str, result: Optional[Any] = None) -> None:
        """Log when a task is completed."""
        self._tasks_completed += 1
        
        event_data = {
            "message": f"Task completed by {agent_name}",
            "task_description": task_description,
            "agent_name": agent_name,
            "crew_name": self.crew_name,
            "task_number": self._tasks_completed
        }
        
        if result is not None:
            event_data["result"] = str(result)[:1000]
        
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data=event_data,
            tags={"framework": "crewai", "event": "task_complete"}
        )
        self.client.emit(event)
    
    def log_collaboration(self, from_agent: str, to_agent: str, message: str) -> None:
        """Log collaboration between agents."""
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            data={
                "message": "Agent collaboration",
                "from_agent": from_agent,
                "to_agent": to_agent,
                "collaboration_message": message,
                "crew_name": self.crew_name
            },
            tags={"framework": "crewai", "event": "collaboration"}
        )
        self.client.emit(event)
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the crew execution."""
        self.run.add_data(key, value)


class AgentTaskContext:
    """Context for tracking an individual agent task."""
    
    def __init__(
        self,
        agent_name: str,
        task_description: str,
        client: TelemetryClient,
        run_id: Optional[str] = None,
        crew_name: Optional[str] = None,
        expected_output: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.agent_name = agent_name
        self.task_description = task_description
        self.client = client
        self.run_id = run_id
        self.crew_name = crew_name
        self.expected_output = expected_output
        self.metadata = metadata or {}
        self._start_time = None
        self._context = None
    
    def __enter__(self):
        self._start_time = time.time()
        
        tags = {"framework": "crewai", "agent": self.agent_name}
        if self.crew_name:
            tags["crew"] = self.crew_name
        
        data = {
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "framework": "crewai",
            **self.metadata
        }
        
        if self.expected_output:
            data["expected_output"] = self.expected_output
        if self.crew_name:
            data["crew_name"] = self.crew_name
        
        self._context = AgentRun(
            name=f"agent_task_{self.agent_name}",
            client=self.client,
            tags=tags,
            data=data
        ).__enter__()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._context:
            self._context.__exit__(exc_type, exc_val, exc_tb)
    
    def set_result(self, result: Any) -> None:
        """Set the task result."""
        if self._context:
            self._context.add_data("result", result)
    
    def log_thinking(self, thought: str) -> None:
        """Log agent thinking/reasoning."""
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run_id,
            span_id=self._context.span_id if self._context else None,
            data={
                "message": "Agent thinking",
                "thought": thought,
                "agent_name": self.agent_name
            },
            tags={"framework": "crewai", "event": "thinking"}
        )
        self.client.emit(event)
    
    def log_action(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log agent action."""
        event_data = {
            "message": f"Agent action: {action}",
            "action": action,
            "agent_name": self.agent_name
        }
        
        if details:
            event_data.update(details)
        
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run_id,
            span_id=self._context.span_id if self._context else None,
            data=event_data,
            tags={"framework": "crewai", "event": "action"}
        )
        self.client.emit(event)


def patch_crewai_crew(crew, adapter: Optional[CrewAdapter] = None):
    """
    Monkey patch a CrewAI Crew to automatically track executions.
    
    Args:
        crew: The CrewAI Crew instance to patch
        adapter: CrewAdapter instance (creates new one if None)
    
    Returns:
        The patched crew
    
    Example:
        from crewai import Crew
        from abide_agentkit.adapters import patch_crewai_crew
        
        crew = Crew(agents=[...], tasks=[...])
        crew = patch_crewai_crew(crew)
        
        # Now executions are automatically tracked
        result = crew.kickoff()
    """
    if adapter is None:
        adapter = CrewAdapter()
    
    # Store original kickoff method
    original_kickoff = crew.kickoff
    
    def tracked_kickoff(*args, **kwargs):
        crew_name = getattr(crew, 'name', 'unnamed_crew')
        agent_names = [getattr(agent, 'role', 'unnamed_agent') for agent in crew.agents]
        task_descriptions = [getattr(task, 'description', 'unnamed_task') for task in crew.tasks]
        
        with adapter.track_crew_execution(
            crew_name=crew_name,
            agents=agent_names,
            tasks=task_descriptions
        ) as crew_context:
            crew_context.set_input(kwargs)
            result = original_kickoff(*args, **kwargs)
            crew_context.set_output(result)
            return result
    
    # Replace kickoff method
    crew.kickoff = tracked_kickoff
    
    return crew
