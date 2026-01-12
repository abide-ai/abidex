"""
Workflow discovery module.

This module provides functionality to discover workflows from log files,
both from registered workflows and through auto-discovery.
"""

import json
import re
from typing import Dict, Optional
from pathlib import Path

import glob

from .registry import WorkflowRegistry
from ..cli_common import get_repo_root
from ..log_patterns import find_log_files, format_log_patterns, resolve_log_patterns


def _extract_workflow_name_from_filename(filename: str) -> Optional[str]:
    """Extract workflow name from filename pattern.
    
    Patterns:
    - {workflow}_logs_*.jsonl → {workflow}
    - {workflow}_telemetry_*.jsonl → {workflow}
    - agent_logs_*.jsonl → agent
    """
    # Pattern: {workflow}_logs_*.jsonl
    match = re.match(r'^(.+?)_logs_.*\.jsonl$', filename)
    if match:
        workflow = match.group(1)
        if workflow != 'agent':  # Don't return 'agent' for generic pattern
            return workflow
    
    # Pattern: {workflow}_telemetry_*.jsonl
    match = re.match(r'^(.+?)_telemetry_.*\.jsonl$', filename)
    if match:
        return match.group(1)
    
    # Pattern: agent_logs_*.jsonl → 'agent'
    if filename.startswith('agent_logs_') and filename.endswith('.jsonl'):
        return 'agent'
    
    return None


def _analyze_log_file_content(file_path: str, max_sample_lines: int = 100) -> dict:
    """Analyze log file content to extract workflow metadata.
    
    Returns dict with:
    - workflow_name: From metadata.workflow_name, tags.workflow, metadata.pipeline
    - display_name: From metadata.workflow_display_name or inferred
    - agents: Set of unique agent names
    - sample_events: Number of events sampled
    """
    result = {
        'workflow_name': None,
        'display_name': None,
        'agents': set(),
        'sample_events': 0,
        'metadata_sources': {}
    }
    
    try:
        with open(file_path, 'r') as f:
            lines_read = 0
            for line in f:
                if lines_read >= max_sample_lines:
                    break
                    
                if not line.strip():
                    continue
                
                try:
                    event = json.loads(line.strip())
                    result['sample_events'] += 1
                    lines_read += 1
                    
                    # Extract workflow name from various sources
                    metadata = event.get('metadata', {})
                    tags = event.get('tags', {})
                    
                    # Check multiple sources for workflow name
                    workflow_name = (
                        metadata.get('workflow_name') or
                        metadata.get('workflow') or
                        metadata.get('pipeline') or
                        tags.get('workflow') or
                        tags.get('pipeline')
                    )
                    
                    if workflow_name and not result['workflow_name']:
                        result['workflow_name'] = workflow_name
                        result['metadata_sources']['workflow_name'] = 'metadata' if metadata.get('workflow_name') else 'tags'
                    
                    # Extract display name
                    display_name = metadata.get('workflow_display_name') or metadata.get('display_name')
                    if display_name and not result['display_name']:
                        result['display_name'] = display_name
                    
                    # Extract agents
                    agent_name = tags.get('agent') or event.get('agent', {}).get('name')
                    if agent_name:
                        result['agents'].add(agent_name)
                        
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        pass
    
    # Convert agents set to list for JSON serialization
    result['agents'] = list(result['agents'])
    
    return result


def _find_matching_script(workflow_name: str, search_dir: Path) -> Optional[str]:
    """Find matching Python script for workflow."""
    patterns = [
        f"{workflow_name}.py",
        f"{workflow_name}_pipeline.py",
        f"{workflow_name}_test.py",
        f"{workflow_name}_agent.py"
    ]

    search_paths = [search_dir, search_dir / "examples"]

    for search_path in search_paths:
        for pattern in patterns:
            matches = glob.glob(str(search_path / pattern))
            if matches:
                return Path(matches[0]).name
    
    return None


def _find_matching_notebook(workflow_name: str, search_dir: Path) -> Optional[str]:
    """Find matching Jupyter notebook for workflow."""
    patterns = [
        f"{workflow_name}_analysis.ipynb",
        f"{workflow_name}_logs_analysis.ipynb",
        f"{workflow_name}.ipynb"
    ]

    # Also check notebooks subdirectory
    search_paths = [
        search_dir,
        search_dir / "notebooks",
        search_dir / "examples",
        search_dir / "examples" / "notebooks",
    ]

    for search_path in search_paths:
        for pattern in patterns:
            matches = glob.glob(str(search_path / pattern))
            if matches:
                return Path(matches[0]).name
    
    return None


def _infer_display_name(workflow_name: str, agents: list) -> str:
    """Infer display name from workflow name and agents.
    
    Examples:
    - fraud_detection → Fraud Detection
    - weather_agent → Weather Agent
    - customer_service → Customer Service
    """
    # If we have agents, try to infer from agent names
    if agents:
        # Use first agent name as hint
        first_agent = agents[0] if agents else ""
        # Remove common suffixes
        agent_base = re.sub(r'(_agent|Agent|_handler|Handler)$', '', first_agent, flags=re.IGNORECASE)
        if agent_base and agent_base != workflow_name:
            # Capitalize and format
            return ' '.join(word.capitalize() for word in agent_base.replace('_', ' ').split())
    
    # Convert workflow_name to display name
    # fraud_detection → Fraud Detection
    display = ' '.join(word.capitalize() for word in workflow_name.replace('_', ' ').split())
    return display


def _analyze_workflow_logs(log_files: list) -> dict:
    """Analyze log files to extract workflow statistics.
    
    Returns dict with: total_events, agents, unique_runs, last_seen
    """
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
                            
                            # Track agents
                            tags = event.get('tags', {})
                            agent_info = event.get('agent', {})
                            
                            agent_name = tags.get('agent')
                            if not agent_name:
                                agent_name = agent_info.get('name')
                            
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
                                
                                if agent_role and not agents[agent_name]['role']:
                                    agents[agent_name]['role'] = agent_role
                                
                                # Track last call
                                call_name = None
                                metadata = event.get('metadata', {})
                                action = event.get('action', {})
                                
                                if tags.get('event_type') == 'action':
                                    call_name = metadata.get('action')
                                elif tags.get('event_type') == 'decision':
                                    call_name = metadata.get('decision')
                                elif action:
                                    call_name = action.get('name')
                                
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
    
    return {
        'total_events': total_events,
        'agents': agents,
        'unique_runs': len(runs),
        'last_seen': last_seen
    }


def discover_workflows(registry: Optional[WorkflowRegistry] = None) -> Dict[str, dict]:
    """Discover workflows from log files and return workflow information.
    
    Phase 1: Process workflows from WorkflowRegistry (loaded from workflows.json)
    Phase 2: Auto-discover new workflows from log files using filename patterns
    Phase 3: Analyze content to extract metadata and enrich workflow information
    
    Args:
        registry: Optional WorkflowRegistry instance. If None, loads default.
    
    Returns dict mapping workflow_id to workflow information.
    """
    if registry is None:
        registry = WorkflowRegistry.load_default()
    
    workflows = {}
    package_dir = get_repo_root()
    
    # Phase 1: Process workflows from WorkflowRegistry (loaded from workflows.json)
    registry_workflow_ids = set()
    for workflow in registry.list():
        workflow_id = workflow.id
        registry_workflow_ids.add(workflow_id)
        log_patterns = workflow.log_patterns
        log_files = find_log_files(log_patterns)
        
        if not log_files:
            continue
        
        # Analyze log files to get workflow stats
        stats = _analyze_workflow_logs(log_files)
        
        # Filter out pipeline/system name from agents if specified
        if workflow.pipeline_name and workflow.pipeline_name in stats['agents']:
            del stats['agents'][workflow.pipeline_name]
        
        workflows[workflow_id] = {
            "display_name": workflow.display_name,
            "log_pattern": format_log_patterns(log_patterns),
            "log_patterns": list(log_patterns),
            "log_files": log_files,
            "notebook": workflow.notebook,
            "script": workflow.script,
            "total_events": stats['total_events'],
            "agents": stats['agents'],
            "unique_runs": stats['unique_runs'],
            "last_seen": stats['last_seen'],
            "source": "registry"  # Mark as from registry
        }
    
    # Phase 2: Auto-discover workflows from log files
    # Scan for log files using patterns
    discovered_files = {}
    auto_patterns = resolve_log_patterns(search_dir=Path.cwd())
    for file_path in find_log_files(auto_patterns):
        filename = Path(file_path).name
        workflow_name = _extract_workflow_name_from_filename(filename)
        
        if workflow_name:
            # Normalize workflow name (use underscore, lowercase)
            workflow_id = workflow_name.lower().replace('-', '_')
            
            # Skip if already in registry
            if workflow_id in registry_workflow_ids:
                continue
            
            # Group files by workflow
            if workflow_id not in discovered_files:
                discovered_files[workflow_id] = []
            discovered_files[workflow_id].append(file_path)
    
    # Phase 3: Analyze content and enrich workflow information
    for workflow_id, log_files in discovered_files.items():
        # Analyze first file to get metadata
        first_file = log_files[0]
        content_analysis = _analyze_log_file_content(first_file)
        
        # Determine workflow name (prefer from content, fallback to filename)
        workflow_name = content_analysis.get('workflow_name') or workflow_id
        
        # Determine display name
        display_name = content_analysis.get('display_name')
        if not display_name:
            # Infer from workflow name and agents
            agents_list = list(content_analysis.get('agents', []))
            display_name = _infer_display_name(workflow_name, agents_list)
        
        # Infer log pattern from discovered files
        # Use the pattern that matches all files
        if len(log_files) == 1:
            filename = Path(log_files[0]).name
            # Extract pattern: fraud_detection_logs_*.jsonl
            match = re.match(r'^(.+?)_(logs|telemetry)_.*\.jsonl$', filename)
            if match:
                log_pattern = f"{match.group(1)}_{match.group(2)}_*.jsonl"
            else:
                log_pattern = f"{workflow_id}_logs_*.jsonl"
        else:
            # Multiple files, use common prefix
            log_pattern = f"{workflow_id}_logs_*.jsonl"
        
        # Find matching script and notebook
        script = _find_matching_script(workflow_name, package_dir)
        notebook = _find_matching_notebook(workflow_name, package_dir)
        
        # Analyze all log files for statistics
        stats = _analyze_workflow_logs(log_files)
        
        # Merge agents from content analysis with stats
        content_agents = content_analysis.get('agents', [])
        for agent_name in content_agents:
            if agent_name not in stats['agents']:
                stats['agents'][agent_name] = {
                    'events': 0,
                    'role': None,
                    'last_call': None,
                    'last_call_time': None
                }
        
        workflows[workflow_id] = {
            "display_name": display_name,
            "log_pattern": log_pattern,
            "log_patterns": [log_pattern],
            "log_files": log_files,
            "notebook": notebook,
            "script": script,
            "total_events": stats['total_events'],
            "agents": stats['agents'],
            "unique_runs": stats['unique_runs'],
            "last_seen": stats['last_seen'],
            "source": "auto_discovered"  # Mark as auto-discovered
        }
    
    return workflows


def resolve_workflow_name(name: str, registry: Optional[WorkflowRegistry] = None) -> Optional[str]:
    """Resolve workflow name or alias to canonical workflow ID.
    
    Checks WorkflowRegistry (from workflows.json) and auto-discovered workflows.
    
    Args:
        name: Workflow name or alias to resolve
        registry: Optional WorkflowRegistry instance. If None, loads default.
    
    Returns:
        Canonical workflow ID or None if not found
    """
    if registry is None:
        registry = WorkflowRegistry.load_default()
    
    # Try resolving through registry (handles aliases)
    workflow = registry.resolve_name(name)
    if workflow:
        return workflow.id
    
    # Check auto-discovered workflows
    workflows = discover_workflows(registry)
    name_lower = name.lower()
    if name_lower in workflows:
        return name_lower
    
    # Try fuzzy match (for auto-discovered workflows)
    # e.g., "fraud-detection" matches "fraud_detection"
    normalized_name = name_lower.replace('-', '_')
    if normalized_name in workflows:
        return normalized_name
    
    return None
