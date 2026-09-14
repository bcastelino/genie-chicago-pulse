import type { PipelineRunResponse } from "../api/types";

const TERMINAL_RUN_STATES = new Set(["TERMINATED", "SKIPPED", "INTERNAL_ERROR"]);

export function isRunTerminal(run: PipelineRunResponse): boolean {
  return TERMINAL_RUN_STATES.has(run.life_cycle_state);
}
