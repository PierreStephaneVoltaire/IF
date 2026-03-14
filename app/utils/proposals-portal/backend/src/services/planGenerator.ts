import { Proposal, Directive } from '@proposals-portal/types';

const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || '';
const PLAN_GENERATION_MODEL = process.env.PLAN_GENERATION_MODEL || '@preset/heavy';

const SYSTEM_PROMPT = `You are generating a precise implementation plan for a developer to execute in Claude Code.

Your output must be a markdown document with the following structure:

## Affected Files
- List all files that need to be modified or created

## Implementation Steps
1. Step-by-step instructions with:
   - Exact file paths
   - Function names to modify
   - Code snippets where helpful
   - No ambiguity

## Test/Validation Steps
- How to verify the changes work correctly

## Rollback Notes (if applicable)
- Any destructive changes or risks
- How to revert if needed

Be specific about file paths, function names, and exact changes. The plan will be copy-pasted directly into Claude Code for execution.`;

export async function generateImplementationPlan(
  proposal: Proposal,
  existingDirectives: Directive[]
): Promise<string> {
  if (!OPENROUTER_API_KEY) {
    throw new Error('OPENROUTER_API_KEY not configured');
  }

  const relevantDirectives = existingDirectives
    .filter((d) => d.active)
    .slice(0, 10); // Limit context

  const directiveContext = relevantDirectives
    .map((d) => `### ${d.label}\n${d.content}`)
    .join('\n\n');

  const targetContext = proposal.target_id
    ? `\n\nTarget directive: ${proposal.target_id}`
    : '';

  const userMessage = `## Proposal Type
${proposal.type}

## Title
${proposal.title}

## Rationale
${proposal.rationale}

## Proposed Content
${proposal.content || 'N/A'}
${targetContext}

## Relevant Existing Directives
${directiveContext || 'None available'}

Generate the implementation plan.`;

  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': 'http://localhost:3004',
      'X-Title': 'Proposals Portal - Plan Generator',
    },
    body: JSON.stringify({
      model: PLAN_GENERATION_MODEL,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: userMessage },
      ],
      max_tokens: 4000,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenRouter API error: ${response.status} - ${error}`);
  }

  const data = await response.json();
  const plan = data.choices?.[0]?.message?.content;

  if (!plan) {
    throw new Error('No plan generated from model');
  }

  return plan;
}
