from __future__ import annotations

import asyncio
from typing import Any, Callable

from abidex.otel_setup import get_tracer

GEN_AI_FRAMEWORK = "gen_ai.framework"
GEN_AI_WORKFLOW_NAME = "gen_ai.workflow.name"
GEN_AI_TEAM_AGENTS = "gen_ai.team.agents"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_ROLE = "gen_ai.agent.role"
GEN_AI_AGENT_GOAL = "gen_ai.agent.goal"
GEN_AI_AGENT_BACKSTORY = "gen_ai.agent.backstory"
GEN_AI_TASK_DESCRIPTION = "gen_ai.task.description"

MAX_STR = 200
GOAL_PREFIX = 80


def _trunc(s: Any, max_len: int = MAX_STR) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    return t[:max_len] + "..." if len(t) > max_len else t


def _crew_workflow_name(crew: Any) -> str:
    if hasattr(crew, "name") and crew.name:
        return str(crew.name).strip()
    return "UnnamedCrew"


def _crew_agent_roles(crew: Any) -> list[str]:
    if not hasattr(crew, "agents") or not crew.agents:
        return []
    roles: list[str] = []
    for ag in crew.agents:
        if hasattr(ag, "role") and ag.role:
            roles.append(str(ag.role).strip())
        elif hasattr(ag, "name") and ag.name:
            roles.append(str(ag.name).strip())
        else:
            roles.append("Unnamed")
    return roles


def _wrap_kickoff(original: Callable[..., Any]) -> Callable[..., Any]:
    def kickoff(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get("self")
        name = _crew_workflow_name(self)
        span_name = f"Workflow: {name}"
        tracer = get_tracer("crewai")
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_WORKFLOW_NAME, name)
            span.set_attribute(GEN_AI_FRAMEWORK, "crewai")
            agents_list = _crew_agent_roles(self)
            if agents_list:
                span.set_attribute(GEN_AI_TEAM_AGENTS, ",".join(agents_list))
            return original(*args, **kwargs)
    return kickoff


def _wrap_akickoff(original: Callable[..., Any]) -> Callable[..., Any]:
    async def akickoff(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get("self")
        name = _crew_workflow_name(self)
        span_name = f"Workflow: {name}"
        tracer = get_tracer("crewai")
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_WORKFLOW_NAME, name)
            span.set_attribute(GEN_AI_FRAMEWORK, "crewai")
            agents_list = _crew_agent_roles(self)
            if agents_list:
                span.set_attribute(GEN_AI_TEAM_AGENTS, ",".join(agents_list))
            return await original(*args, **kwargs)
    return akickoff


def _agent_display_role(agent: Any) -> str:
    if hasattr(agent, "role") and agent.role:
        return str(agent.role).strip()
    if hasattr(agent, "name") and agent.name:
        return str(agent.name).strip()
    return "Unnamed"


def _agent_goal_preview(agent: Any) -> str:
    if not hasattr(agent, "goal") or not agent.goal:
        return ""
    g = str(agent.goal).strip()
    return g[:GOAL_PREFIX] + "..." if len(g) > GOAL_PREFIX else g


def _wrap_execute_task(original: Callable[..., Any]) -> Callable[..., Any]:
    def execute_task(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get("self")
        task = args[1] if len(args) > 1 else kwargs.get("task")
        role = _agent_display_role(self)
        goal_preview = _agent_goal_preview(self)
        span_name = f"Agent: {role} | Goal: {goal_preview}" if goal_preview else f"Agent: {role}"
        tracer = get_tracer("crewai")
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_AGENT_NAME, getattr(self, "name", None) or "Unnamed")
            if hasattr(self, "role") and self.role:
                span.set_attribute(GEN_AI_AGENT_ROLE, str(self.role))
            if hasattr(self, "goal") and self.goal:
                span.set_attribute(GEN_AI_AGENT_GOAL, _trunc(self.goal, MAX_STR))
            if hasattr(self, "backstory") and self.backstory:
                span.set_attribute(GEN_AI_AGENT_BACKSTORY, _trunc(self.backstory, MAX_STR))
            if task is not None and hasattr(task, "description") and task.description:
                span.set_attribute(GEN_AI_TASK_DESCRIPTION, _trunc(task.description, MAX_STR))
            span.add_event("agent.start")
            try:
                result = original(*args, **kwargs)
                summary = _trunc(str(result), MAX_STR) if result is not None else "ok"
                span.add_event("agent.complete", {"result_summary": summary})
                return result
            except Exception as e:
                span.record_exception(e)
                span.add_event("agent.complete", {"error": str(e)[:MAX_STR]})
                raise
    return execute_task


def _wrap_execute_task_async(original: Callable[..., Any]) -> Callable[..., Any]:
    async def execute_task_async(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get("self")
        task = args[1] if len(args) > 1 else kwargs.get("task")
        role = _agent_display_role(self)
        goal_preview = _agent_goal_preview(self)
        span_name = f"Agent: {role} | Goal: {goal_preview}" if goal_preview else f"Agent: {role}"
        tracer = get_tracer("crewai")
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_AGENT_NAME, getattr(self, "name", None) or "Unnamed")
            if hasattr(self, "role") and self.role:
                span.set_attribute(GEN_AI_AGENT_ROLE, str(self.role))
            if hasattr(self, "goal") and self.goal:
                span.set_attribute(GEN_AI_AGENT_GOAL, _trunc(self.goal, MAX_STR))
            if hasattr(self, "backstory") and self.backstory:
                span.set_attribute(GEN_AI_AGENT_BACKSTORY, _trunc(self.backstory, MAX_STR))
            if task is not None and hasattr(task, "description") and task.description:
                span.set_attribute(GEN_AI_TASK_DESCRIPTION, _trunc(task.description, MAX_STR))
            span.add_event("agent.start")
            try:
                result = await original(*args, **kwargs)
                summary = _trunc(str(result), MAX_STR) if result is not None else "ok"
                span.add_event("agent.complete", {"result_summary": summary})
                return result
            except Exception as e:
                span.record_exception(e)
                span.add_event("agent.complete", {"error": str(e)[:MAX_STR]})
                raise
    return execute_task_async


def _patch_crew(crew_cls: type) -> None:
    if getattr(crew_cls.kickoff, "_patched", False):
        return
    original_kickoff = crew_cls.kickoff
    crew_cls.kickoff = _wrap_kickoff(original_kickoff)
    crew_cls.kickoff._patched = True
    if hasattr(crew_cls, "akickoff"):
        original_akickoff = crew_cls.akickoff
        crew_cls.akickoff = _wrap_akickoff(original_akickoff)
        crew_cls.akickoff._patched = True


def _patch_agent(agent_cls: type) -> None:
    for method_name in ("execute_task", "do_task"):
        if not hasattr(agent_cls, method_name):
            continue
        method = getattr(agent_cls, method_name)
        if getattr(method, "_patched", False):
            continue
        if asyncio.iscoroutinefunction(method):
            setattr(agent_cls, method_name, _wrap_execute_task_async(method))
        else:
            setattr(agent_cls, method_name, _wrap_execute_task(method))
        getattr(agent_cls, method_name)._patched = True
        break


def apply_crewai_patch() -> bool:
    try:
        from crewai import Crew, Agent, Task
    except ImportError:
        return False
    _patch_crew(Crew)
    _patch_agent(Agent)
    return True
