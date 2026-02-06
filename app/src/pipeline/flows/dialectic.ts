import { createLogger } from '../../utils/logger';
import { MODEL_TIERS } from '../../modules/agentic/escalation';
import { chatCompletion, extractContent } from '../../modules/litellm/index';
import { streamProgressToDiscord } from '../../modules/agentic/progress';
import type { FlowContext, FlowResult } from './types';

const log = createLogger('FLOW:DIALECTIC');

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
 * Dialectic Synthesis Flow
 *
 * Thesis → Antithesis → Synthesis
 * For philosophical/abstract questions seeking understanding, not decision-making.
 *
 * Pattern: Sequential (not parallel) - antithesis needs to see thesis
 */
export async function executeDialecticFlow(
    context: FlowContext
): Promise<FlowResult> {
    log.info('Phase: DIALECTIC_FLOW');

    const userQuestion = context.history.current_message;

    // 1. Select 2 random tier2 models (must be different)
    const [thesisModel, antithesisModel] = getRandomModelsFromTier('tier2', 2);
    if (!antithesisModel) {
        // Fallback if tier only has 1 model
        log.warn('Only one tier2 model available, using same model for thesis and antithesis');
    }
    const antithesisModelActual = antithesisModel || getRandomModelFromTier('tier2');

    // 2. Select 1 random tier4 synthesizer
    const synthesizerModel = getRandomModelFromTier('tier4');

    log.info(`Using thesis model: ${thesisModel}`);
    log.info(`Using antithesis model: ${antithesisModelActual}`);
    log.info(`Using synthesizer model: ${synthesizerModel}`);

    // 3. Generate Thesis
    log.info('Generating thesis...');
    await streamProgressToDiscord(context.workspaceId, {
        type: 'dialectic',
        phase: 'thesis',
        model: thesisModel
    });

    const thesisPrompt = `You are a philosopher presenting the strongest possible THESIS on the following question.

## User's Question
"${userQuestion}"

## Your Task
Present the strongest, most compelling THESIS (one philosophical position) on this question.

## Guidelines
- Present the strongest case for ONE coherent philosophical position
- Use rigorous reasoning and clear argumentation
- Acknowledge complexities but defend your position firmly
- This is the "thesis" that will be countered by an antithesis

## Format
1. **Position Statement**: Clear statement of your philosophical position (2-3 sentences)
2. **Core Arguments**: 3-5 key arguments supporting this position
3. **Underlying Assumptions**: What assumptions does this position rest on?
4. **Philosophical Tradition**: What school of thought does this represent? (e.g., utilitarianism, existentialism, Kantian ethics, etc.)

Be thorough and persuasive. This is the opening move in a dialectical exploration.`;

    const thesisResponse = await chatCompletion({
        model: thesisModel,
        messages: [{ role: 'user', content: thesisPrompt }],
    });
    const thesis = extractContent(thesisResponse);
    log.info(`Thesis generated, length: ${thesis.length}`);

    // 4. Generate Antithesis (aware of thesis)
    log.info('Generating antithesis...');
    await streamProgressToDiscord(context.workspaceId, {
        type: 'dialectic',
        phase: 'antithesis',
        model: antithesisModelActual
    });

    const antithesisPrompt = `You are a philosopher presenting the strongest possible ANTITHESIS to the following thesis.

## User's Original Question
"${userQuestion}"

## The Thesis You Must Counter
${thesis}

## Your Task
Present the strongest, most compelling ANTITHESIS (opposing philosophical position) to the thesis above.

## Guidelines
- This must be a genuine philosophical counter-position, not just nitpicking
- Attack the core assumptions and reasoning of the thesis
- Present an alternative framework that leads to different conclusions
- Be rigorous and persuasive - this is a serious philosophical challenge

## Format
1. **Counter-Position Statement**: Clear statement of your opposing position (2-3 sentences)
2. **Critique of Thesis**: What are the fundamental flaws in the thesis?
3. **Alternative Arguments**: 3-5 key arguments for your counter-position
4. **Different Assumptions**: What different assumptions lead to your conclusion?
5. **Philosophical Tradition**: What opposing school of thought does this represent?

Be thorough and compelling. This antithesis should create genuine philosophical tension with the thesis.`;

    const antithesisResponse = await chatCompletion({
        model: antithesisModelActual,
        messages: [{ role: 'user', content: antithesisPrompt }],
    });
    const antithesis = extractContent(antithesisResponse);
    log.info(`Antithesis generated, length: ${antithesis.length}`);

    // 5. Generate Synthesis
    log.info('Generating synthesis...');
    await streamProgressToDiscord(context.workspaceId, {
        type: 'dialectic',
        phase: 'synthesis',
        model: synthesizerModel
    });

    const synthesisPrompt = `You are a master philosopher tasked with synthesizing a thesis and antithesis into a higher-order understanding.

## User's Original Question
"${userQuestion}"

## The Thesis
${thesis}

## The Antithesis
${antithesis}

## Your Task
Create a SYNTHESIS that transcends both the thesis and antithesis.

## Guidelines for Synthesis
- Do not simply compromise or average the two positions
- Find a higher-order framework that incorporates the valid insights from both
- Identify what each position gets right and what it misses
- Show how the apparent contradiction can be resolved or reframed
- The synthesis should provide deeper understanding than either position alone

## Format
1. **Summary of Positions**: Brief, fair summary of both thesis and antithesis (2-3 sentences each)
2. **Key Tension**: What is the fundamental tension between these positions?
3. **What Thesis Gets Right**: Valid insights from the thesis position
4. **What Antithesis Gets Right**: Valid insights from the antithesis position
5. **Limitations of Both**: What does each position fail to account for?
6. **The Synthesis**: Your higher-order resolution (3-5 paragraphs)
   - Present a framework that incorporates both insights
   - Show how the contradiction dissolves at a higher level of analysis
   - Provide a richer, more nuanced understanding of the question
7. **Remaining Questions**: What aspects remain unresolved or require further exploration?

This synthesis should give the user a layered, sophisticated understanding of the philosophical question.`;

    const synthesisResponse = await chatCompletion({
        model: synthesizerModel,
        messages: [{ role: 'user', content: synthesisPrompt }],
    });
    const synthesis = extractContent(synthesisResponse);
    log.info(`Synthesis generated, length: ${synthesis.length}`);

    // 6. Return the synthesis
    return {
        response: synthesis,
        model: synthesizerModel,
        responseChannelId: context.channelId,
    };
}