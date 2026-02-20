"""
Adapter for integrating with CrewAI framework.
"""

import time
import json
import ast
from typing import Any, Dict, List, Optional, Callable
from contextlib import contextmanager

from ..client import TelemetryClient, get_client, Event, EventType
from ..spans import AgentRun, ToolCall
from ..utils.id_utils import generate_run_id

class CrewAdapter:
    """
    Adapter for tracking CrewAI crew executions, agent tasks, and tool usage.
    
    Based on patterns from financial-insight-agentic-flow repository.
    """
    
    def __init__(self, client: Optional[TelemetryClient] = None):
        self.client = client or get_client()
        self._active_runs: Dict[str, str] = {}  # crew_id -> run_id mapping
        self._agent_registry: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent_metadata
        self._task_registry: Dict[str, Dict[str, Any]] = {}  # task_id -> task_metadata
    
    @staticmethod
    def _extract_json_from_text(text: str, expect: str = "object") -> str:
        """Best-effort extraction of a JSON object/array from model output.
        
        Args:
            text: Raw LLM/Crew output
            expect: "object" or "array"
        
        Returns:
            Extracted JSON substring
        
        Based on financial-insight-agentic-flow/src/agents/crew.py
        """
        if not text:
            raise ValueError("Empty output")

        # Prefer fenced blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                candidate = text[start:end].strip()
                # If it's clearly the right shape, take it.
                if expect == "array" and "[" in candidate:
                    return candidate
                if expect == "object" and "{" in candidate:
                    return candidate

        # Balanced extraction (handles trailing prose after JSON)
        open_ch = "{" if expect == "object" else "["
        close_ch = "}" if expect == "object" else "]"
        start = text.find(open_ch)
        if start == -1:
            raise ValueError(f"No JSON {expect} start found")

        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            else:
                if ch == '"':
                    in_str = True
                    continue
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1].strip()

        # Fallback: naive slice to last closing delimiter
        end = text.rfind(close_ch)
        if end == -1 or end <= start:
            raise ValueError(f"No JSON {expect} end found")
        return text[start : end + 1].strip()
    
    @staticmethod
    def _parse_jsonish(text: str) -> Any:
        """Parse either strict JSON or Python-literal dict/list (single quotes).
        
        Based on financial-insight-agentic-flow/src/agents/crew.py
        """
        try:
            return json.loads(text)
        except Exception:
            # Crew outputs sometimes look like Python dicts (single quotes)
            return ast.literal_eval(text)
    
    def track_agent_creation(
        self,
        agent,
        crew_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track the creation of a CrewAI Agent.
        
        Args:
            agent: CrewAI Agent instance
            crew_name: Name of the parent crew (if applicable)
            metadata: Additional agent metadata
        
        Returns:
            Agent ID for reference
        
        Example:
            agent = Agent(role="Researcher", goal="Find information", ...)
            agent_id = adapter.track_agent_creation(agent, crew_name="research_crew")
        """
        agent_id = id(agent)
        role = getattr(agent, 'role', 'unnamed_agent')
        goal = getattr(agent, 'goal', '')
        backstory = getattr(agent, 'backstory', '')
        verbose = getattr(agent, 'verbose', False)
        allow_delegation = getattr(agent, 'allow_delegation', False)
        
        agent_data = {
            "agent_id": str(agent_id),
            "role": role,
            "goal": goal,
            "backstory": backstory[:500] if backstory else "",  # Truncate long backstories
            "verbose": verbose,
            "allow_delegation": allow_delegation,
            "framework": "crewai",
            **(metadata or {})
        }
        
        if crew_name:
            agent_data["crew_name"] = crew_name
        
        self._agent_registry[str(agent_id)] = agent_data
        
        # Emit event for agent creation
        event = Event(
            event_type=EventType.LOG,
            run_id=self._active_runs.get(crew_name) if crew_name else None,
            metadata={
                "message": f"Agent created: {role}",
                "event": "agent_creation",
                **agent_data
            },
            tags={"framework": "crewai", "event": "agent_creation", "agent_role": role}
        )
        self.client.emit(event)
        
        return str(agent_id)
    
    def track_task_creation(
        self,
        task,
        crew_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track the creation of a CrewAI Task.
        
        Args:
            task: CrewAI Task instance
            crew_name: Name of the parent crew (if applicable)
            metadata: Additional task metadata
        
        Returns:
            Task ID for reference
        
        Example:
            task = Task(description="Research topic", expected_output="Report", agent=agent)
            task_id = adapter.track_task_creation(task, crew_name="research_crew")
        """
        task_id = id(task)
        description = getattr(task, 'description', 'unnamed_task')
        expected_output = getattr(task, 'expected_output', '')
        agent = getattr(task, 'agent', None)
        agent_role = getattr(agent, 'role', None) if agent else None
        
        task_data = {
            "task_id": str(task_id),
            "description": description[:1000] if description else "",  # Truncate long descriptions
            "expected_output": expected_output[:500] if expected_output else "",
            "agent_role": agent_role,
            "framework": "crewai",
            **(metadata or {})
        }
        
        if crew_name:
            task_data["crew_name"] = crew_name
        
        self._task_registry[str(task_id)] = task_data
        
        # Emit event for task creation
        event = Event(
            event_type=EventType.LOG,
            run_id=self._active_runs.get(crew_name) if crew_name else None,
            metadata={
                "message": f"Task created: {description[:100]}",
                "event": "task_creation",
                **task_data
            },
            tags={"framework": "crewai", "event": "task_creation"}
        )
        self.client.emit(event)
        
        return str(task_id)
    
    @contextmanager
    def track_crew_execution(
        self,
        crew_name: str,
        agents: Optional[List[str]] = None,
        tasks: Optional[List[str]] = None,
        process: Optional[str] = None,
        verbose: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracking a CrewAI crew execution.
        
        Args:
            crew_name: Name of the crew being executed
            agents: List of agent names/roles in the crew
            tasks: List of task descriptions
            process: Process type (e.g., "sequential", "hierarchical")
            verbose: Whether crew is running in verbose mode
            metadata: Additional metadata about the crew
        
        Yields:
            CrewExecutionContext for tracking the crew execution
        
        Example:
            adapter = CrewAdapter()
            with adapter.track_crew_execution(
                "research_crew", 
                agents=["Researcher", "Writer"],
                process="sequential"
            ) as crew:
                crew.set_input({"topic": "AI trends"})
                result = crew.kickoff()
                crew.set_output(result)
        """
        run_id = generate_run_id("crew")
        
        crew_data = {
            "crew_name": crew_name,
            "agents": agents or [],
            "tasks": tasks or [],
            "framework": "crewai",
            **(metadata or {})
        }
        
        if process:
            crew_data["process"] = process
        if verbose is not None:
            crew_data["verbose"] = verbose
        
        with AgentRun(
            name=f"crew_{crew_name}",
            client=self.client,
            data=crew_data,
            tags={"framework": "crewai", "crew": crew_name}
        ) as run:
            context = CrewExecutionContext(run, crew_name, self.client)
            self._active_runs[crew_name] = run.run_id
            
            try:
                yield context
            finally:
                if crew_name in self._active_runs:
                    del self._active_runs[crew_name]
    
    def track_crew_object(
        self,
        crew,
        crew_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track a CrewAI Crew object and extract its configuration.
        
        Args:
            crew: CrewAI Crew instance
            crew_name: Optional name for the crew (defaults to extracting from crew)
            metadata: Additional metadata
        
        Returns:
            Crew name/ID
        
        Example:
            crew = Crew(agents=[agent1, agent2], tasks=[task1], process=Process.sequential)
            crew_id = adapter.track_crew_object(crew)
        """
        if crew_name is None:
            crew_name = getattr(crew, 'name', f'crew_{id(crew)}')
        
        # Extract agent information
        agents = getattr(crew, 'agents', [])
        agent_roles = []
        agent_details = []
        for agent in agents:
            role = getattr(agent, 'role', 'unnamed_agent')
            agent_roles.append(role)
            agent_details.append({
                "role": role,
                "goal": getattr(agent, 'goal', '')[:200],
                "verbose": getattr(agent, 'verbose', False),
                "allow_delegation": getattr(agent, 'allow_delegation', False)
            })
            # Track agent creation
            self.track_agent_creation(agent, crew_name=crew_name)
        
        # Extract task information
        tasks = getattr(crew, 'tasks', [])
        task_descriptions = []
        task_details = []
        for task in tasks:
            description = getattr(task, 'description', 'unnamed_task')
            task_descriptions.append(description[:200])
            task_details.append({
                "description": description[:500],
                "expected_output": getattr(task, 'expected_output', '')[:200],
                "agent_role": getattr(getattr(task, 'agent', None), 'role', None) if getattr(task, 'agent', None) else None
            })
            # Track task creation
            self.track_task_creation(task, crew_name=crew_name)
        
        # Extract process type
        process = getattr(crew, 'process', None)
        process_str = str(process) if process else None
        
        # Extract verbose setting
        verbose = getattr(crew, 'verbose', None)
        
        crew_metadata = {
            "agent_details": agent_details,
            "task_details": task_details,
            "process": process_str,
            "verbose": verbose,
            **(metadata or {})
        }
        
        # Emit event for crew creation
        event = Event(
            event_type=EventType.LOG,
            metadata={
                "message": f"Crew created: {crew_name}",
                "event": "crew_creation",
                "crew_name": crew_name,
                "num_agents": len(agents),
                "num_tasks": len(tasks),
                **crew_metadata
            },
            tags={"framework": "crewai", "event": "crew_creation", "crew": crew_name}
        )
        self.client.emit(event)
        
        return crew_name
    
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
            metadata={
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
            metadata=event_data,
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
            metadata=event_data,
            tags={"framework": "crewai", "event": "task_complete"}
        )
        self.client.emit(event)
    
    def log_collaboration(self, from_agent: str, to_agent: str, message: str) -> None:
        """Log collaboration between agents."""
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            metadata={
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
    
    def parse_json_output(self, output: Any, expect: str = "object") -> Any:
        """
        Parse JSON from CrewAI output (handles code fences and text wrapping).
        
        Args:
            output: Raw output from crew.kickoff()
            expect: "object" or "array" - expected JSON type
        
        Returns:
            Parsed JSON object or array
        
        Example:
            result = crew.kickoff()
            parsed = crew_context.parse_json_output(result, expect="object")
        """
        result_str = str(output)
        try:
            json_str = CrewAdapter._extract_json_from_text(result_str, expect=expect)
            return CrewAdapter._parse_jsonish(json_str)
        except Exception as e:
            self.log_error(f"Failed to parse JSON output: {e}")
            return None
    
    def log_error(self, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """Log an error during crew execution."""
        event_data = {
            "message": f"Crew error: {error_message}",
            "crew_name": self.crew_name,
            **(error_details or {})
        }
        
        event = Event(
            event_type=EventType.ERROR,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            metadata=event_data,
            tags={"framework": "crewai", "event": "error", "crew": self.crew_name}
        )
        self.client.emit(event)
    
    def log_stage_complete(self, stage_name: str, stage_data: Optional[Dict[str, Any]] = None) -> None:
        """Log completion of a workflow stage (useful for multi-stage workflows)."""
        event_data = {
            "message": f"Stage complete: {stage_name}",
            "stage_name": stage_name,
            "crew_name": self.crew_name,
            **(stage_data or {})
        }
        
        event = Event(
            event_type=EventType.LOG,
            run_id=self.run.run_id,
            span_id=self.run.span_id,
            metadata=event_data,
            tags={"framework": "crewai", "event": "stage_complete", "crew": self.crew_name}
        )
        self.client.emit(event)


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
            metadata={
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
            metadata=event_data,
            tags={"framework": "crewai", "event": "action"}
        )
        self.client.emit(event)


def patch_crewai_crew(crew, adapter: Optional[CrewAdapter] = None):
    """
    Monkey patch a CrewAI Crew to automatically track executions.
    
    This function wraps the crew.kickoff() method to automatically track:
    - Crew configuration (agents, tasks, process)
    - Input parameters
    - Execution results
    - Errors and timing
    
    Args:
        crew: The CrewAI Crew instance to patch
        adapter: CrewAdapter instance (creates new one if None)
    
    Returns:
        The patched crew
    
    Example:
        from crewai import Crew, Process
        from abidex.adapters.crew_adapter import patch_crewai_crew
        
        crew = Crew(agents=[agent1, agent2], tasks=[task1], process=Process.sequential)
        crew = patch_crewai_crew(crew)
        
        # Now executions are automatically tracked
        result = crew.kickoff(inputs={"topic": "AI trends"})
    """
    if adapter is None:
        adapter = CrewAdapter()
    
    # Track crew object configuration
    crew_name = adapter.track_crew_object(crew)
    
    # Store original kickoff method
    original_kickoff = crew.kickoff
    
    def tracked_kickoff(*args, **kwargs):
        # Extract crew configuration
        agent_names = [getattr(agent, 'role', 'unnamed_agent') for agent in getattr(crew, 'agents', [])]
        task_descriptions = [getattr(task, 'description', 'unnamed_task')[:200] for task in getattr(crew, 'tasks', [])]
        process = getattr(crew, 'process', None)
        process_str = str(process) if process else None
        verbose = getattr(crew, 'verbose', None)
        
        with adapter.track_crew_execution(
            crew_name=crew_name,
            agents=agent_names,
            tasks=task_descriptions,
            process=process_str,
            verbose=verbose
        ) as crew_context:
            # Track input parameters
            input_data = {}
            if args:
                input_data["args"] = str(args)[:500]
            if kwargs:
                input_data.update({k: str(v)[:500] for k, v in kwargs.items()})
            crew_context.set_input(input_data)
            
            # Track execution
            start_time = time.time()
            try:
                result = original_kickoff(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track output
                output_str = str(result)
                crew_context.set_output({
                    "result_preview": output_str[:1000],  # Truncate for storage
                    "result_length": len(output_str),
                    "duration_seconds": duration
                })
                
                # Log successful completion
                crew_context.log_stage_complete("crew_execution", {
                    "duration_seconds": duration,
                    "result_length": len(output_str)
                })
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                crew_context.log_error(
                    str(e),
                    {
                        "error_type": type(e).__name__,
                        "duration_seconds": duration
                    }
                )
                raise
    
    # Replace kickoff method
    crew.kickoff = tracked_kickoff
    
    return crew
