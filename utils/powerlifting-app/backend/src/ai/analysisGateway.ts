import axios from 'axios'
import { 
  LLM_BASE_URL, 
  OPENROUTER_API_KEY, 
  IMPORT_FAST_MODEL, 
  IMPORT_PARSE_MODEL, 
  ANALYSIS_MODEL,
  ANALYSIS_MODEL_THINKING_BUDGET
} from './config'
import * as prompts from './prompts'

export class AnalysisGateway {
  private static async callLLM(model: string, systemPrompt: string, userMessage: any, toolSchema?: any, toolName?: string) {
    if (!OPENROUTER_API_KEY) {
      throw new Error('OPENROUTER_API_KEY is not set')
    }

    const payload: any = {
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: JSON.stringify(userMessage, null, 2) }
      ]
    }

    if (toolSchema && toolName) {
      payload.tools = [{ type: 'function', function: toolSchema }]
      payload.tool_choice = { type: 'function', function: { name: toolName } }
    }

    if (model === ANALYSIS_MODEL) {
      payload.thinking = { type: 'enabled', budget_tokens: ANALYSIS_MODEL_THINKING_BUDGET }
    }

    const response = await axios.post(`${LLM_BASE_URL}/chat/completions`, payload, {
      headers: {
        'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
        'Content-Type': 'application/json'
      },
      timeout: 120000 // 2 minutes
    })

    const message = response.data.choices[0].message
    if (message.tool_calls && message.tool_calls.length > 0) {
      return JSON.parse(message.tool_calls[0].function.arguments)
    }

    // Fallback to content parsing if tool calls not used
    const content = message.content.trim()
    if (content.startsWith('{')) {
      return JSON.parse(content)
    }

    throw new Error('LLM did not return structured JSON')
  }

  static async classify(rowsSample: any[]) {
    return this.callLLM(
      IMPORT_FAST_MODEL,
      prompts.IMPORT_CLASSIFY_SYSTEM_PROMPT,
      { rows_sample: rowsSample },
      {
        name: 'report_classification',
        description: 'Report the classification of a training program file',
        parameters: {
          type: 'object',
          properties: {
            classification: { type: 'string', enum: ['template', 'session_import', 'ambiguous'] },
            confidence: { type: 'number' },
            reasoning: { type: 'string' },
            ambiguity_reason: { type: 'string' }
          },
          required: ['classification', 'confidence', 'reasoning']
        }
      },
      'report_classification'
    )
  }

  static async parse(rows: any[]) {
    return this.callLLM(
      IMPORT_PARSE_MODEL,
      prompts.IMPORT_PARSE_SYSTEM_PROMPT,
      { rows },
      {
        name: 'report_parse_result',
        description: 'Report the structured parse result of a training program',
        parameters: {
          type: 'object',
          properties: {
            phases: { type: 'array', items: { type: 'object' } },
            sessions: { type: 'array', items: { type: 'object' } },
            required_maxes: { type: 'array', items: { type: 'string' } },
            warnings: { type: 'array', items: { type: 'object' } },
            parse_notes: { type: 'string' }
          },
          required: ['phases', 'sessions', 'required_maxes', 'warnings', 'parse_notes']
        }
      },
      'report_parse_result'
    )
  }

  static async resolveGlossary(exerciseNames: string[], existingGlossary: any[]) {
    return this.callLLM(
      IMPORT_FAST_MODEL,
      prompts.GLOSSARY_RESOLVE_SYSTEM_PROMPT,
      {
        exercise_names_from_file: exerciseNames,
        existing_glossary: existingGlossary.map(ex => ({ id: ex.id, name: ex.name }))
      },
      {
        name: 'report_glossary_resolution',
        description: 'Report the resolution of exercise names to glossary IDs',
        parameters: {
          type: 'object',
          properties: {
            resolutions: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  input: { type: 'string' },
                  matched_id: { type: ['string', 'null'] },
                  confidence: { type: 'number' },
                  method: { type: 'string', enum: ['exact', 'abbreviation', 'nickname', 'no_match'] },
                  suggested_new_entry: {
                    type: 'object',
                    properties: {
                      name: { type: 'string' },
                      category: { type: 'string' },
                      equipment: { type: 'string' }
                    }
                  }
                },
                required: ['input', 'matched_id', 'confidence', 'method']
              }
            }
          },
          required: ['resolutions']
        }
      },
      'report_glossary_resolution'
    )
  }

  static async backfillE1rm(missingExercises: string[], currentMaxes: any) {
    return this.callLLM(
      IMPORT_FAST_MODEL,
      prompts.E1RM_BACKFILL_SYSTEM_PROMPT,
      {
        missing_exercises: missingExercises,
        current_maxes: currentMaxes
      },
      {
        name: 'report_e1rm_estimates',
        description: 'Report estimated e1RMs for accessory exercises',
        parameters: {
          type: 'object',
          properties: {
            estimates: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  exercise: { type: 'string' },
                  e1rm_kg: { type: 'number' },
                  ratio: { type: 'number' },
                  primary_lift_used: { type: 'string', enum: ['squat', 'bench', 'deadlift'] },
                  basis: { type: 'string' },
                  confidence: { type: 'string', enum: ['medium', 'low'] }
                },
                required: ['exercise', 'e1rm_kg', 'ratio', 'primary_lift_used', 'basis', 'confidence']
              }
            }
          },
          required: ['estimates']
        }
      },
      'report_e1rm_estimates'
    )
  }

  static async evaluateTemplate(template: any, athleteContext: any) {
    return this.callLLM(
      ANALYSIS_MODEL,
      prompts.TEMPLATE_EVALUATE_SYSTEM_PROMPT,
      { template, athlete_context: athleteContext },
      {
        name: 'report_template_evaluation',
        description: 'Report the evaluation of a training template',
        parameters: {
          type: 'object',
          properties: {
            stance: { type: 'string', enum: ['continue', 'monitor', 'adjust', 'critical'] },
            summary: { type: 'string' },
            strengths: { type: 'array', items: { type: 'string' } },
            weaknesses: { type: 'array', items: { type: 'string' } },
            suggestions: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  type: { type: 'string' },
                  week: { type: ['number', 'null'] },
                  phase: { type: ['string', 'null'] },
                  exercise: { type: ['string', 'null'] },
                  rationale: { type: 'string' }
                },
                required: ['type', 'rationale']
              }
            },
            projected_readiness_at_comp: { type: 'number' },
            data_citations: { type: 'array', items: { type: 'string' } }
          },
          required: ['stance', 'summary', 'strengths', 'weaknesses', 'suggestions', 'projected_readiness_at_comp']
        }
      },
      'report_template_evaluation'
    )
  }
}
