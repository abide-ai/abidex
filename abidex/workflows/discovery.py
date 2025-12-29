import json
from typing import Dict

import glob

from .registry import WorkflowRegistry


def discover_workflows(registry: WorkflowRegistry) -> Dict[str, dict]:
    """Discover workflows from log files and return workflow information."""
    workflows = {}

    for workflow in registry.list():
        log_files = glob.glob(workflow.log_pattern)

        if not log_files:
            continue

        # Analyze log files to get workflow stats
        total_events = 0
        agents = {}
        last_seen = None
        runs = set()

        for file_path in log_files:
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                event = json.loads(line.strip())
                                total_events += 1

                                # Track agents - prioritize tags['agent'] (set by AgentLogger) over agent.name
                                tags = event.get('tags', {})
                                agent_info = event.get('agent', {})

                                # AgentLogger sets agent name in tags, prioritize that
                                agent_name = tags.get('agent')
                                if not agent_name:
                                    # Fall back to agent.name if tags don't have it
                                    agent_name = agent_info.get('name')

                                # Also get role from tags or agent field
                                agent_role = tags.get('role') or agent_info.get('role')

                                if agent_name:
                                    if agent_name not in agents:
                                        agents[agent_name] = {
                                            'events': 0,
                                            'role': agent_role,
                                            'last_call': None,
                                            'last_call_time': None
                                        }
                                    agents[agent_name]['events'] += 1
                                    # Update role if we found one
                                    if agent_role and not agents[agent_name]['role']:
                                        agents[agent_name]['role'] = agent_role

                                    # Track last call - check multiple sources
                                    call_name = None
                                    metadata = event.get('metadata', {})
                                    action = event.get('action', {})

                                    # For AgentLogger events, action is in metadata
                                    if tags.get('event_type') == 'action':
                                        # AgentLogger stores action in metadata.action
                                        call_name = metadata.get('action')
                                    elif tags.get('event_type') == 'decision':
                                        call_name = metadata.get('decision')
                                    # For regular events, check action.name
                                    elif action:
                                        call_name = action.get('name')
                                    # Fallback to metadata
                                    if not call_name:
                                        call_name = metadata.get('action') or metadata.get('agent_action')

                                    if call_name:
                                        telemetry = event.get('telemetry', {})
                                        timestamp = telemetry.get('timestamp_start')
                                        if timestamp:
                                            if (agents[agent_name]['last_call_time'] is None or
                                                timestamp > agents[agent_name]['last_call_time']):
                                                agents[agent_name]['last_call'] = call_name
                                                agents[agent_name]['last_call_time'] = timestamp

                                    # Track timestamp
                                    telemetry = event.get('telemetry', {})
                                    timestamp = telemetry.get('timestamp_start')
                                    if timestamp:
                                        if last_seen is None or timestamp > last_seen:
                                            last_seen = timestamp

                                # Track runs
                                run_id = event.get('run_id')
                                if run_id:
                                    runs.add(run_id)
                            except (json.JSONDecodeError, KeyError):
                                pass
            except Exception:
                pass

        # Filter out pipeline/system name from agents if specified
        if workflow.pipeline_name and workflow.pipeline_name in agents:
            del agents[workflow.pipeline_name]

        workflows[workflow.id] = {
            "display_name": workflow.display_name,
            "log_pattern": workflow.log_pattern,
            "log_files": log_files,
            "notebook": workflow.notebook,
            "script": workflow.script,
            "total_events": total_events,
            "agents": agents,
            "unique_runs": len(runs),
            "last_seen": last_seen
        }

    return workflows
