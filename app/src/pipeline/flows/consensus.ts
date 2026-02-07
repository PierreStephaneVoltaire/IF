import { createLogger } from '../../utils/logger';
import { MODEL_TIERS } from '../../modules/agentic/escalation';
import { chatCompletion, extractContent } from '../../modules/litellm/index';
import { streamProgressToDiscord } from '../../modules/agentic/progress';
import { getModelParams } from '../../modules/langgraph/temperature';
import { FlowType } from '../../modules/litellm/types';
import type { FlowContext, FlowResult } from './types';

const log = createLogger('FLOW:CONSENSUS');

/**
 * Select N random models from a tier
 */
function getRandomModelsFromTier(tier: keyof typeof MODEL_TIERS, count: number): string[] {
    const tierModels = [...MODEL_TIERS[tier]];
    // Shuffle array
    for (let i = tierModels.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [tierModels[i], tierModels[j]] = [tierModels[j], tierModels[i]];
    }
    return tierModels.slice(0, Math.min(count, tierModels.length));
}

/**
 * Select 1 random model from a tier
 */
function getRandomModelFromTier(tier: keyof typeof MODEL_TIERS): string {
    const tierModels = MODEL_TIERS[tier];
    const randomIndex = Math.floor(Math.random() * tierModels.length);
    return tierModels[randomIndex];
}

/**
 * Multi-Source Consensus Flow
 *
 * 3 independent models answer → Judge synthesizes
 * For factual questions, trivia, "is it true that..."
 *
 * Pattern: Parallel independent answers → Judge
 */
export async function executeConsensusFlow(
    context: FlowContext
): Promise<FlowResult> {
    log.info('Phase: CONSENSUS_FLOW');

    const userQuestion = context.history.current_message;

    // 1. Select 3 random tier2 models (all different)
    const independentModels = getRandomModelsFromTier('tier2', 3);
    // Ensure we have at least 3 models, fill with random if needed
    while (independentModels.length < 3) {
        const additional = getRandomModelFromTier('tier2');
        if (!independentModels.includes(additional)) {
            independentModels.push(additional);
        }
    }

    // 2. Select 1 random tier4 judge
    const judgeModel = getRandomModelFromTier('tier4');

    const params = getModelParams(FlowType.CONSENSUS);
    log.info(`Using independent models: ${independentModels.join(', ')}`);
    log.info(`Using judge model: ${judgeModel}`);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // 3. Generate independent answers in parallel
    log.info('Generating independent answers in parallel...');

    await Promise.all([
        streamProgressToDiscord(context.workspaceId, {
            type: 'consensus',
            consensusPhase: 'independent',
            model: independentModels[0]
        }),
        streamProgressToDiscord(context.workspaceId, {
            type: 'consensus',
            consensusPhase: 'independent',
            model: independentModels[1]
        }),
        streamProgressToDiscord(context.workspaceId, {
            type: 'consensus',
            consensusPhase: 'independent',
            model: independentModels[2]
        }),
    ]);

    const independentPrompt = `You are answering a factual question independently and thoroughly.

## User's Question
"${userQuestion}"

## Your Task
Provide a complete, accurate answer to this factual question.

## Guidelines
- Answer as thoroughly and accurately as possible
- Base your answer on your training knowledge
- If you're uncertain about any aspect, acknowledge it
- Do not reference other models or consensus - this is your independent answer
- Include specific details, dates, numbers, or facts when relevant

## Format
1. **Direct Answer**: Clear answer to the question (1-3 sentences)
2. **Detailed Explanation**: Elaborate with supporting facts and context
3. **Confidence Level**: State your confidence (High/Medium/Low) and why
4. **Key Facts**: Bullet points of the most important facts
5. **Caveats**: Any uncertainties, edge cases, or "it depends" factors

Provide your best independent answer.`;

    const [response1, response2, response3] = await Promise.all([
        chatCompletion({
            model: independentModels[0],
            messages: [{ role: 'user', content: independentPrompt }],
            temperature: params.temperature,
            top_p: params.top_p,
        }),
        chatCompletion({
            model: independentModels[1],
            messages: [{ role: 'user', content: independentPrompt }],
            temperature: params.temperature,
            top_p: params.top_p,
        }),
        chatCompletion({
            model: independentModels[2],
            messages: [{ role: 'user', content: independentPrompt }],
            temperature: params.temperature,
            top_p: params.top_p,
        }),
    ]);

    const answer1 = extractContent(response1);
    const answer2 = extractContent(response2);
    const answer3 = extractContent(response3);

    log.info(`Independent answers generated: ${answer1.length}, ${answer2.length}, ${answer3.length} chars`);

    // 4. Judge synthesizes consensus
    log.info('Judge synthesizing consensus...');
    await streamProgressToDiscord(context.workspaceId, {
        type: 'consensus',
        consensusPhase: 'judging',
        model: judgeModel
    });

    const judgePrompt = `You are a fact-checking judge analyzing three independent answers to determine consensus or disagreement.

## User's Original Question
"${userQuestion}"

## Independent Answer 1 (from ${independentModels[0]})
${answer1}

## Independent Answer 2 (from ${independentModels[1]})
${answer2}

## Independent Answer 3 (from ${independentModels[2]})
${answer3}

## Your Task
Analyze these three answers and synthesize a final response for the user.

## Guidelines
- Compare the answers for factual agreement and disagreement
- Identify points of consensus (all three agree)
- Identify points of disagreement (answers diverge)
- Note any unique insights from individual answers
- Assess overall confidence based on agreement level

## Format Your Response

### Consensus Assessment
State the overall level of agreement: **Strong Consensus** / **Partial Consensus** / **Significant Disagreement**

### Agreed-Upon Facts
List facts that all three answers agree on (if any):
- Fact 1
- Fact 2
...

### Points of Disagreement
If answers disagree, clearly state:
- **Topic of disagreement**: What do they disagree about?
- **Position A**: What one answer claims
- **Position B**: What another answer claims
- **Assessment**: Your evaluation of which is more likely correct, or if it's genuinely uncertain

### Synthesized Answer
Provide a clear, balanced answer that:
- Presents the consensus view when it exists
- Acknowledges uncertainty when models disagree
- Explains the nature of any disagreements
- Gives the user the most reliable information available

### Confidence Indicator
**High Confidence**: Strong consensus across all three models
**Medium Confidence**: Partial consensus with minor disagreements
**Low Confidence**: Significant disagreement or high uncertainty

Your response should help the user understand both what is reliably known and where there is uncertainty.`;

    const judgeResponse = await chatCompletion({
        model: judgeModel,
        messages: [{ role: 'user', content: judgePrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
    });
    const synthesis = extractContent(judgeResponse);
    log.info(`Consensus synthesis generated, length: ${synthesis.length}`);

    // 5. Return the synthesis
    return {
        response: synthesis,
        model: judgeModel,
        responseChannelId: context.channelId,
    };
}