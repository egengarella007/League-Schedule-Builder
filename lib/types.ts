import { z } from "zod";

// Database types
export type Slot = {
  id: number;
  league_id: string;
  type: string | null;
  event_start: string; // ISO
  event_end: string;   // ISO
  resource: string | null;
  created_at: string;
};

export type Division = {
  id: number;
  league_id: string;
  name: string;
  created_at: string;
};

export type Team = {
  id: number;
  league_id: string;
  division_id: number;
  name: string;
  created_at: string;
};

export type League = {
  id: string;
  name: string;
  created_at: string;
};

export type SchedulerParams = {
  id: number;
  league_id: string;
  name: string;
  params: SchedulerParamsData;
  created_at: string;
};

export type Run = {
  id: number;
  league_id: string;
  params_id: number | null;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  result_url: string | null;
  kpis: any | null;
  logs: any | null;
  created_at: string;
  error: string | null;
};

// Parameters schema (shared, versioned)
export const ParamsSchema = z.object({
  timezone: z.string().default("America/Chicago"),

  // Hard rules
  noBackToBack: z.boolean().default(true),
  subDivisionCrossover: z.boolean().default(false),
  noInterdivision: z.boolean().default(true),
  minRestDays: z.number().int().min(0).default(3),
  maxGapDays: z.number().int().min(1).default(12),

  // Gap Management (unified: bias + smoothing)
  idealGapDays: z.number().int().min(3).max(14).default(7),

  // E/M/L cutoffs (UI says "games starting before this time)
  eml: z.object({
    earlyStart: z.string().default("22:01"),
    midStart: z.string().default("22:31"),
  }),

  // Season settings
  gamesPerTeam: z.number().int().min(1).default(12),

  // Balance goals + weights
  weekdayBalance: z.boolean().default(true),
  varianceMinimization: z.boolean().default(true),
  homeAwayBalance: z.boolean().default(true), // enhancement
  holidayAwareness: z.boolean().default(true),

  weights: z.object({
    gapBias: z.number().min(0).max(10).default(1.0),
    idleUrgency: z.number().min(0).max(10).default(8.0),
    emlBalance: z.number().min(0).max(10).default(5.0),
    weekRotation: z.number().min(0).max(10).default(4.0),
    weekdayBalance: z.number().min(0).max(10).default(0.5),
    homeAway: z.number().min(0).max(10).default(0.5),
  }),

  // Misc
  seed: z.number().int().default(42),
});

export type SchedulerParamsData = z.infer<typeof ParamsSchema>;

// Default parameters
export const DEFAULT_PARAMS: SchedulerParamsData = {
  timezone: "America/Chicago",
  noBackToBack: true,
  subDivisionCrossover: false,
  noInterdivision: true,
  minRestDays: 3,
  maxGapDays: 12,
  idealGapDays: 7,
  eml: {
    earlyStart: "22:01",
    midStart: "22:31",
  },
  gamesPerTeam: 12,
  weekdayBalance: true,
  varianceMinimization: true,
  homeAwayBalance: true,
  holidayAwareness: true,
  weights: {
    gapBias: 1.0,
    idleUrgency: 8.0,
    emlBalance: 5.0,
    weekRotation: 4.0,
    weekdayBalance: 0.5,
    homeAway: 0.5,
  },
  seed: 42,
};

// API response types
export type ScheduleResponse = {
  runId: number;
  url: string;
  kpis: {
    max_gap: number;
    avg_gap: number;
    swaps: number;
    early_games: number;
    mid_games: number;
    late_games: number;
  };
};

export type ScheduleError = {
  error: string;
  details?: string;
};
