/**
 * AI Model Configuration for Portals Backend
 */

export const LLM_BASE_URL = process.env.LLM_BASE_URL || 'https://openrouter.ai/api/v1'
export const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || ''

// Model Tiers
export const IMPORT_FAST_MODEL = process.env.IMPORT_FAST_MODEL || 'anthropic/claude-3-haiku-20240307'
export const IMPORT_PARSE_MODEL = process.env.IMPORT_PARSE_MODEL || 'anthropic/claude-3.5-sonnet'
export const ANALYSIS_MODEL = process.env.ANALYSIS_MODEL || 'anthropic/claude-3-opus'
export const ANALYSIS_MODEL_THINKING_BUDGET = parseInt(process.env.ANALYSIS_MODEL_THINKING_BUDGET || '4000', 10)
