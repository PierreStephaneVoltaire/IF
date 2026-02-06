import { createLogger } from '../../utils/logger';
import { MODEL_TIERS } from '../../modules/agentic/escalation';
import { chatCompletion, extractContent } from '../../modules/litellm/index';
import { streamProgressToDiscord } from '../../modules/agentic/progress';
import type { FlowContext, FlowResult } from './types';

const log = createLogger('FLOW:ANGEL_DEVIL');

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
 * Angel/Devil Debate Flow
 *
 * Angel argues FOR → Devil argues AGAINST → Judge synthesizes
 * For moral/ethical dilemmas, "should I..." questions
 *
 * Pattern: Parallel adversarial → Judge
 */
export async function executeAngelDevilFlow(
    context: FlowContext
): Promise<FlowResult> {
    log.info('Phase: ANGEL_DEVIL_FLOW');

    const userQuestion = context.history.current_message;

    // 1. Select 2 random tier2 models (must be different)
    const [angelModel, devilModel] = getRandomModelsFromTier('tier2', 2);
    const devilModelActual = devilModel || getRandomModelFromTier('tier2');

    // 2. Select 1 random tier4 judge
    const judgeModel = getRandomModelFromTier('tier4');

    log.info(`Using angel model: ${angelModel}`);
    log.info(`Using devil model: ${devilModelActual}`);
    log.info(`Using judge model: ${judgeModel}`);

    // 3. Generate arguments in parallel
    log.info('Generating angel and devil arguments in parallel...');

    await Promise.all([
        streamProgressToDiscord(context.workspaceId, {
            type: 'angel_devil',
            angelDevilPhase: 'debating',
            model: angelModel
        }),
        streamProgressToDiscord(context.workspaceId, {
            type: 'angel_devil',
            angelDevilPhase: 'debating',
            model: devilModelActual
        }),
    ]);

    const angelPrompt = `You are the ANGEL - arguing the strongest possible case FOR the following question.

## User's Question
"${userQuestion}"

## Your Role: THE ANGEL (Advocate FOR)
Your job is to make the strongest, most compelling case FOR this position. You are the "angel on the shoulder" arguing why this is the right choice.

## Guidelines
- This is an adversarial debate - argue your side with full conviction
- Present the strongest ethical, practical, and emotional arguments FOR
- Consider benefits, positive outcomes, moral justifications
- Anticipate and preemptively counter the obvious objections
- Use persuasive rhetoric and compelling examples
- Do not hedge or be balanced - this is a debate, not a balanced essay

## Format
1. **Core Position**: Clear statement of what you're arguing FOR (1-2 sentences)
2. **Ethical Arguments**: Why is this the morally right choice?
3. **Practical Benefits**: What good outcomes will result?
4. **Countering Objections**: Address the strongest arguments against your position
5. **Emotional Appeal**: Why does this feel like the right choice?
6. **Conclusion**: Powerful summary of why the user should choose FOR

Argue with passion and conviction. You are the angel advocating for the best choice.`;

    const devilPrompt = `You are the DEVIL - arguing the strongest possible case AGAINST the following question.

## User's Question
"${userQuestion}"

## Your Role: THE DEVIL (Advocate AGAINST)
Your job is to make the strongest, most compelling case AGAINST this position. You are the "devil on the shoulder" arguing why this is the wrong choice.

## Guidelines
- This is an adversarial debate - argue your side with full conviction
- Present the strongest ethical, practical, and emotional arguments AGAINST
- Consider risks, negative outcomes, moral hazards, unintended consequences
- Anticipate and preemptively counter the obvious pro arguments
- Use persuasive rhetoric and compelling cautionary examples
- Do not hedge or be balanced - this is a debate, not a balanced essay

## Format
1. **Core Position**: Clear statement of what you're arguing AGAINST (1-2 sentences)
2. **Ethical Concerns**: Why might this be the morally wrong choice?
3. **Risks and Downsides**: What negative outcomes could result?
4. **Unintended Consequences**: What might go wrong?
5. **Countering Pro Arguments**: Address the strongest arguments for the other side
6. **Conclusion**: Powerful summary of why the user should choose AGAINST

Argue with passion and conviction. You are the devil's advocate warning against the wrong choice.`;

    const [angelResponse, devilResponse] = await Promise.all([
        chatCompletion({
            model: angelModel,
            messages: [{ role: 'user', content: angelPrompt }],
        }),
        chatCompletion({
            model: devilModelActual,
            messages: [{ role: 'user', content: devilPrompt }],
        }),
    ]);

    const angelArgument = extractContent(angelResponse);
    const devilArgument = extractContent(devilResponse);

    log.info(`Angel argument: ${angelArgument.length} chars`);
    log.info(`Devil argument: ${devilArgument.length} chars`);

    // 4. Judge synthesizes balanced response
    log.info('Judge synthesizing balanced response...');
    await streamProgressToDiscord(context.workspaceId, {
        type: 'angel_devil',
        angelDevilPhase: 'judging',
        model: judgeModel
    });

    const judgePrompt = `You are a wise judge synthesizing a balanced, nuanced response from an angel/devil debate.

## User's Original Question
"${userQuestion}"

## The Angel's Argument (FOR)
${angelArgument}

## The Devil's Argument (AGAINST)
${devilArgument}

## Your Task
Create a balanced, nuanced synthesis that helps the user understand both sides and make an informed decision.

## Guidelines
- Do not simply pick a winner - both sides have valid points
- Present the strongest arguments from each side fairly
- Help the user understand the trade-offs and tensions
- Provide a framework for decision-making, not just a verdict
- Acknowledge when the "right" answer depends on values/priorities
- Be empathetic to the difficulty of the choice

## Format Your Response

### The Dilemma
Briefly frame what makes this a difficult choice (2-3 sentences)

### The Case For (Angel's Perspective)
Fair summary of the strongest pro arguments:
- Key point 1
- Key point 2
- Key point 3

### The Case Against (Devil's Perspective)
Fair summary of the strongest con arguments:
- Key point 1
- Key point 2
- Key point 3

### The Tension
What is the fundamental conflict here? What values or priorities are in tension?

### Decision Framework
Help the user think through this by considering:
- If you value X most, then...
- If you prioritize Y, then...
- Questions to ask yourself...

### Final Reflection
A thoughtful closing that acknowledges the difficulty of the choice and offers wisdom without being preachy.

Your goal is not to tell the user what to do, but to help them understand the full landscape of the decision so they can choose wisely.`;

    const judgeResponse = await chatCompletion({
        model: judgeModel,
        messages: [{ role: 'user', content: judgePrompt }],
    });
    const synthesis = extractContent(judgeResponse);
    log.info(`Balanced synthesis generated, length: ${synthesis.length}`);

    // 5. Return the synthesis
    return {
        response: synthesis,
        model: judgeModel,
        responseChannelId: context.channelId,
    };
}