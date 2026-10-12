/** Wire types of the console API (mirrors src/deepgym/console/schemas.py). */

export type EnvKind = 'single-turn' | 'multi-turn' | 'computer-use';

export interface EnvironmentSummary {
  id: string;
  name: string;
  kind: EnvKind;
  type: string;
  difficulty: string;
  domain: string;
  family: string;
  tags: string[];
  variants: number;
}

export interface EnvironmentDetail extends EnvironmentSummary {
  variant: number;
  task: string;
  verifier: string;
  reference: string | null;
  metadata: Record<string, unknown>;
}

export const RUN_MODES = ['local', 'docker', 'apple', 'daytona', 'modal', 'e2b', 'auto'] as const;
export type RunMode = (typeof RUN_MODES)[number];
export type RunStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface CaseResult {
  id: string;
  passed: boolean;
  score: number;
  input_summary: string;
  expected_summary: string;
  actual_summary: string;
  error: string | null;
  execution_time_ms: number;
}

export interface RunResult {
  score: number;
  passed: boolean;
  output: string;
  stderr: string;
  exit_code: number;
  execution_time_ms: number;
  sandbox_id: string;
  reward_components: Record<string, number> | null;
  error_type: string | null;
  cases: CaseResult[] | null;
}

export interface RunSummary {
  id: string;
  group_id: string;
  environment: string;
  mode: RunMode;
  provider: string;
  reference: boolean;
  status: RunStatus;
  score: number | null;
  passed: boolean | null;
  error_type: string | null;
  duration_ms: number | null;
  created_at: string;
  finished_at: string | null;
}

export interface RunDetail extends RunSummary {
  solution: string;
  error: string | null;
  result: RunResult | null;
}

export interface Action {
  action_type: string;
  content: string;
  x: number | null;
  y: number | null;
  to_x: number | null;
  to_y: number | null;
  path: string | null;
  amount: number;
}

export interface Frame {
  index: number;
  content: string;
  done: boolean;
  metadata: Record<string, unknown> | null;
  action: Action | null;
  reward: number | null;
  has_screenshot: boolean;
}

export interface EpisodeSummary {
  id: string;
  environment: string;
  steps: number;
  total_reward: number;
  score: number | null;
  passed: boolean | null;
  created_at: string;
}

export interface EpisodeDetail extends EpisodeSummary {
  frames: Frame[];
  result: RunResult | null;
}

export interface RunningSandbox {
  id: string;
  image: string;
  state: string;
  started: string;
}

export interface ProviderSandboxes {
  provider: 'apple' | 'docker';
  available: boolean;
  error: string | null;
  sandboxes: RunningSandbox[];
}

export interface QACheck {
  name: string;
  passed: boolean;
  details: string;
}

export interface QAReport {
  file: string;
  environment: string;
  passed: boolean;
  checks: QACheck[];
  created_at: string;
}
