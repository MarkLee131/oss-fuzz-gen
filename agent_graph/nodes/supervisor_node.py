"""
Supervisor node for LangGraph workflow routing.

This module provides the routing logic for the fuzzing workflow,
determining which agents to execute next based on the current state.
"""
from typing import Dict, Any, List

from langchain_core.runnables import RunnableConfig
import logger
from agent_graph.state import FuzzingWorkflowState, consolidate_session_memory

def supervisor_node(state: FuzzingWorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Supervisor node that determines the next action in the workflow.
    
    This node implements the routing logic based on:
    1. Current workflow state
    2. Success/failure of previous steps
    3. Available analysis results
    4. Maximum retry limits
    
    Design choice:
    - We intentionally let unexpected exceptions bubble up instead of swallowing
      them into "errors" state so that workflow bugs are surfaced early.
    
    Args:
        state: Current LangGraph workflow state
        config: Configuration containing workflow parameters
        
    Returns:
        Dictionary with next_action and routing decisions
    """
    trial = state["trial"]
    logger.info('Starting Supervisor node', trial=trial)
    
    # Check for errors that should terminate the workflow
    errors = state.get("errors", [])
    configurable = config.get("configurable", {})
    max_errors = configurable.get("max_errors", 5)
    if len(errors) >= max_errors:
        logger.warning('Too many errors, terminating workflow', trial=trial)
        return {
            "next_action": "END",
            "termination_reason": "too_many_errors",
            "messages": [{
                "role": "assistant",
                "content": f"Workflow terminated due to {len(errors)} errors"
            }]
        }
    
    # Check retry count
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", configurable.get("max_retries", 3))
    
    if retry_count >= max_retries:
        logger.warning('Maximum retries reached, terminating workflow', trial=trial)
        return {
            "next_action": "END",
            "termination_reason": "max_retries_reached",
            "messages": [{
                "role": "assistant",
                "content": f"Workflow terminated after {retry_count} retries"
            }]
        }
    
    # Routing logic based on current state
    next_action = _determine_next_action(state)
    
    # Track per-node visit counts (similar to no_coverage_improvement_count)
    node_visit_counts = state.get("node_visit_counts", {}).copy()
    if next_action != "END":
        node_visit_counts[next_action] = node_visit_counts.get(next_action, 0) + 1
        
        # Check if a single node is being visited too many times
        MAX_NODE_VISITS = 10
        if node_visit_counts[next_action] > MAX_NODE_VISITS:
            logger.warning(f'Node {next_action} visited {node_visit_counts[next_action]} times, '
                          f'possible loop detected', trial=trial)
            return {
                "next_action": "END",
                "termination_reason": "node_loop_detected",
                "node_visit_counts": node_visit_counts,
                "messages": [{
                    "role": "assistant",
                    "content": f"Workflow terminated: {next_action} visited {node_visit_counts[next_action]} times"
                }]
            }
    
    logger.info(f'Supervisor determined next action: {next_action} '
               f'(node visits: {node_visit_counts.get(next_action, 0)})', 
               trial=trial)
    
    # 整理和清理session_memory，确保下游agent获得干净的共识约束
    session_memory = consolidate_session_memory(state)
    
    return {
        "next_action": next_action,
        "node_visit_counts": node_visit_counts,
        "session_memory": session_memory,  # 注入清理后的共识
        "messages": [{
            "role": "assistant",
            "content": f"Supervisor routing to: {next_action}"
        }]
    }

def _determine_next_action(state: FuzzingWorkflowState) -> str:
    """
    Determine the next action based on current workflow state.
    
    This implements TWO-PHASE routing logic:
    
    PHASE 1: COMPILATION (focus on getting code to compile)
    1. Function analysis -> Prototyper
    2. Prototyper -> Build
    3. Build failed -> Enhancer (max 3 retries)
    4. Still failing after 3 retries -> Regenerate with Prototyper (once)
    5. Compilation succeeds -> Switch to OPTIMIZATION phase
    
    PHASE 2: OPTIMIZATION (focus on runtime validation & bug finding)
    1. Execution -> Analyze results
    2. Crashes -> CrashAnalyzer -> CrashFeasibilityAnalyzer
    3. Feasible crash (true bug) -> END
    4. Non‑crash failures -> at most one Enhancer round, then END
    5. Successful execution without bug -> log coverage once, then END
    
    Args:
        state: Current workflow state
        
    Returns:
        Next action to take
    """
    workflow_phase = state.get("workflow_phase", "compilation")
    trial = state.get("trial", 0)
    
    # Step 1: Check if we need function analysis (required for both phases)
    if not state.get("function_analysis"):
        return "function_analyzer"
    
    # Step 2: Check if we need a fuzz target
    fuzz_target_source = state.get("fuzz_target_source")
    if not fuzz_target_source:
        logger.debug(f'No fuzz_target_source found, routing to prototyper', trial=trial)
        return "prototyper"
    else:
        logger.debug(f'fuzz_target_source exists (length={len(fuzz_target_source)})', trial=trial)
    
    # ===== PHASE 1: COMPILATION =====
    if workflow_phase == "compilation":
        logger.debug(f'In COMPILATION phase', trial=trial)
        
        # Check if we've built successfully
        compile_success = state.get("compile_success")
        logger.debug(f'compile_success={compile_success}', trial=trial)
        
        if compile_success is None:
            # Haven't tried building yet
            return "build"
        
        elif not compile_success:
            # Build failed - handle compilation retry logic
            compilation_retry_count = state.get("compilation_retry_count", 0)
            
            logger.debug(f'Build failed, compilation_retry_count={compilation_retry_count}', trial=trial)
            # Strategy: Try fixer up to 3 times, then end
            MAX_COMPILATION_RETRIES = 3
            
            if compilation_retry_count < MAX_COMPILATION_RETRIES:
                # Try to fix with fixer
                logger.info(f'Compilation failed (attempt {compilation_retry_count + 1}/{MAX_COMPILATION_RETRIES}), '
                           f'routing to fixer', trial=trial)
                return "fixer"
            else:
                # Fixer retries exhausted - give up
                logger.error(f'Compilation failed after {MAX_COMPILATION_RETRIES} fixer retries. Ending workflow.', 
                            trial=trial)
                return "END"
        
        else:
            # Compilation succeeded - check validation
            # Note: BuilderRunner's _pre_build_check validates target function call
            # If validation fails, it sets build_errors with specific message
            
            # Check build_errors for validation failure
            build_errors = state.get("build_errors", [])
            has_validation_error = any(
                "was not called by the fuzz target" in str(err) 
                for err in build_errors
            )
            
            if has_validation_error:
                # Validation failed - target function not called
                validation_failure_count = state.get("validation_failure_count", 0) + 1
                MAX_VALIDATION_RETRIES = 2  # Allow 2 retries for validation fixes
                
                logger.warning(
                    f"🚨 Validation failed: target function not called in driver "
                    f"(attempt {validation_failure_count}/{MAX_VALIDATION_RETRIES})"
                )
                
                if validation_failure_count < MAX_VALIDATION_RETRIES:
                    logger.info(
                        f"Routing to fixer to fix validation error (attempt {validation_failure_count}/{MAX_VALIDATION_RETRIES})",
                        trial=trial
                    )
                    # Return fixer, let fixer node handle the validation error
                    return "fixer"
                else:
                    logger.error(
                        f"Validation failed after {MAX_VALIDATION_RETRIES} retries. "
                        f"Driver does not call target function. Ending workflow.",
                        trial=trial
                    )
                    return "END"
            
            # Validation passed - switch to optimization phase
            logger.info(f'Compilation and validation successful! Switching to OPTIMIZATION phase', trial=trial)
            # Note: The phase switch will be handled by build_node when it updates state
            return "execution"
    
    # ===== PHASE 2: OPTIMIZATION =====
    elif workflow_phase == "optimization":
        logger.debug(f'In OPTIMIZATION phase', trial=trial)
        
        # Build succeeded, check if we've run
        run_success = state.get("run_success")
        logger.debug(f'Build succeeded, run_success={run_success}', trial=trial)
        if run_success is None:
            # Haven't tried running yet
            return "execution"
        
        # We've run, analyze the results
        if not run_success:
            # Execution failed/crashed
            run_error = state.get("run_error", "")
            crashes = state.get("crashes", False)
            
            if crashes or (run_error and "crash" in run_error.lower()):
                # We have a crash to analyze
                crash_analysis = state.get("crash_analysis")
                if not crash_analysis:
                    logger.debug('Crash detected, routing to crash_analyzer', trial=trial)
                    return "crash_analyzer"
                
                # We have crash analysis, check if we need crash feasibility analysis
                context_analysis = state.get("context_analysis")
                if not context_analysis:
                    logger.debug('Crash analyzed, routing to crash_feasibility_analyzer', trial=trial)
                    return "crash_feasibility_analyzer"
                
                # Both crash and context analysis done
                # If crash is feasible (true bug), we're done successfully
                if context_analysis.get("feasible", False):
                    logger.info('Found a feasible crash (true bug)!', trial=trial)
                    return "END"
                else:
                    # False positive, try to fix the target based on recommendations
                    logger.info('Crash is not feasible, fixing target', trial=trial)
                    return "fixer"
            
            # === Non-crash failures (e.g., timeouts, infra errors) ===
            # These are expensive to keep retrying because each fixer round can
            # trigger a full build + run + coverage cycle.
            run_error_str = str(run_error or "").lower()
            timeout_keywords = ("timed out", "timeout", "time-out")
            
            # Special-case: pure timeout → don't even try fixer; just stop.
            if any(kw in run_error_str for kw in timeout_keywords):
                logger.warning(
                    f'Execution failed due to timeout (run_error={run_error_str[:200]}...), '
                    f'skipping fixer and ending workflow',
                    trial=trial
                )
                return "END"
            
            # For other non-crash failures, allow only a very small number of
            # fixer attempts in OPTIMIZATION phase before giving up.
            optimization_fixer_count = state.get("optimization_fixer_count", 0)
            MAX_OPTIMIZATION_ENHANCER_RETRIES = 1
            
            if optimization_fixer_count >= MAX_OPTIMIZATION_ENHANCER_RETRIES:
                logger.info(
                    f'Execution failed (not a crash) and fixer already used '
                    f'{optimization_fixer_count} time(s) in optimization phase, '
                    f'ending workflow instead of looping.',
                    trial=trial
                )
                return "END"
            
            logger.debug(
                f'Execution failed (not a crash), fixing target '
                f'(optimization_fixer_count={optimization_fixer_count + 1}/'
                f'{MAX_OPTIMIZATION_ENHANCER_RETRIES})',
                trial=trial
            )
            return "fixer"
        
        # We only log the final coverage numbers once for observability and then end.
        coverage_percent = state.get("coverage_percent", 0.0)
        coverage_diff = state.get("line_coverage_diff", 0.0)
        total_pcs = state.get("total_pcs", 0)
        
        logger.info(
            f'Execution succeeded; ending workflow '
            f'(PC_coverage={coverage_percent:.2%}, '
            f'line_diff={coverage_diff:.2%}, total_pcs={total_pcs})',
            trial=trial
        )
        return "END"
    
    # Unknown phase - shouldn't happen
    logger.error(f'Unknown workflow phase: {workflow_phase}', trial=trial)
    return "END"

def route_condition(state: FuzzingWorkflowState) -> str:
    """
    LangGraph conditional routing function.
    
    Args:
        state: Current workflow state
        
    Returns:
        Name of the next node to execute
    """
    if "next_action" not in state:
        # Treat missing routing decision as a hard error instead of silently ending
        raise KeyError("Workflow state is missing required 'next_action' for routing")
    
    next_action = state["next_action"]
    
    # Map actions to node names
    action_to_node = {
        "function_analyzer": "function_analyzer",
        "prototyper": "prototyper", 
        "fixer": "fixer",
        "build": "build",
        "execution": "execution",
        "crash_analyzer": "crash_analyzer",
        "coverage_analyzer": "coverage_analyzer",
        "crash_feasibility_analyzer": "crash_feasibility_analyzer",
        "END": "__end__"
    }
    
    if next_action not in action_to_node:
        raise ValueError(f"Unknown next_action for routing: {next_action}")
    
    return action_to_node[next_action]

__all__ = ['supervisor_node', 'route_condition']
