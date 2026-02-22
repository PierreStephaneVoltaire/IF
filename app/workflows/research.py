"""Research workflow for current information retrieval.

This workflow handles the 'research' reasoning pattern where the websearch
agent is invoked first to gather current information, then a domain agent
uses that research to formulate a response.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from streaming import ConversationStream

from models import WorkflowResult
from .base import WorkflowBase, WorkflowContext, AgentInvocation


RESEARCH_QUERY_PROMPT = """Based on this query, generate effective search queries to find current information.

Query: {query}

Context:
{context}

Generate 1-3 search queries that would find the most relevant and current information.
Output as JSON: {{"queries": ["query1", "query2", ...]}}"""

RESEARCH_SYNTHESIS_PROMPT = """You are a research synthesis agent. Based on the following research results,
provide a comprehensive answer to the user's query.

## User Query
{query}

## Research Results
{research_results}

## Instructions
1. Synthesize the research into a coherent response
2. Cite sources where appropriate
3. Note the date/recency of information if available
4. Acknowledge any gaps in the research
5. Flag any conflicting information found

Provide a thorough, evidence-based response."""


class ResearchWorkflow(WorkflowBase):
    """Research workflow for queries requiring current information.
    
    Flow:
    1. Generate search queries based on the user's question
    2. Execute websearch agent (or use Perplexity for deep research)
    3. Present research results to user for confirmation
    4. Synthesize research with domain expertise
    5. Return comprehensive response with citations
    """
    
    @property
    def name(self) -> str:
        return "research"
    
    @property
    def pattern(self) -> str:
        return "research"
    
    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        """Execute research workflow.
        
        Args:
            context: The workflow context
            
        Returns:
            WorkflowResult with research-backed response
        """
        await self.emit_progress("Initiating research phase...")
        
        # Step 1: Generate search queries
        await self.emit_progress("Generating search queries...")
        queries = await self._generate_search_queries(context)
        
        await self.emit_progress(
            f"Generated {len(queries)} search queries",
            metadata={"queries": queries}
        )
        
        # Step 2: Execute research using websearch agent
        await self.emit_progress("Conducting web research...")
        research_results = await self._execute_research(context, queries)
        
        # Step 3: Present research to user (if streaming)
        if self.stream and research_results:
            summary = self._summarize_research(research_results)
            sources = research_results.get("sources", [])
            
            user_response = await self.stream.emit_research_results(
                research_summary=summary,
                sources=sources,
            )
            
            # Handle user response
            if user_response:
                if user_response.selected_option_id == "skip":
                    # User wants to skip research, use simple workflow
                    from .simple import SimpleWorkflow
                    simple = SimpleWorkflow(self.stream)
                    return await simple.execute(context)
                elif user_response.selected_option_id == "refine":
                    # User wants to refine - could add interactive refinement here
                    await self.emit_progress("Refining search with additional queries...")
                    # For now, continue with current results
        
        # Step 4: Synthesize research with domain expertise
        await self.emit_progress("Synthesizing research with domain expertise...")
        
        agent_config = self.get_agent_config(context.category)
        model = agent_config.get("model", "google/gemini-3-flash-preview")
        system_prompt = agent_config.get("system_prompt", "")
        
        synthesis_prompt = RESEARCH_SYNTHESIS_PROMPT.format(
            query=context.condensed_intent,
            research_results=json.dumps(research_results, indent=2),
        )
        
        synthesis_invocation = AgentInvocation(
            agent_name=f"{context.category}_researcher",
            model=model,
            system_prompt=system_prompt,
            user_prompt=synthesis_prompt,
        )
        
        synthesis_response = await self.call_agent(
            synthesis_invocation,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        # Build final response
        sources_section = ""
        if research_results.get("sources"):
            sources_section = "\n\n## Sources\n"
            for source in research_results["sources"]:
                sources_section += f"- [{source.get('title', 'Source')}]({source.get('url', '#')})\n"
        
        final_content = f"""## Research-Based Analysis

{synthesis_response}
{sources_section}"""
        
        return WorkflowResult(
            success=True,
            content=final_content,
            raw_response=synthesis_response,
            agent_name=context.category,
            model=model,
            metadata={
                "workflow": self.name,
                "queries": queries,
                "research_results": research_results,
            },
        )
    
    async def _generate_search_queries(self, context: WorkflowContext) -> List[str]:
        """Generate effective search queries for the user's question."""
        from categorization import call_openrouter
        
        task_context = self.build_user_prompt(context)
        prompt = RESEARCH_QUERY_PROMPT.format(
            query=context.condensed_intent,
            context=task_context,
        )
        
        messages = [{"role": "user", "content": prompt}]
        result = await call_openrouter("google/gemini-3-flash-preview", messages)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Parse queries from response
        try:
            # Clean the response
            content = content.strip()
            if "```" in content:
                content = content.split("```")[1] if "```json" in content else content
                content = content.replace("json", "").strip()
            
            data = json.loads(content)
            return data.get("queries", [context.condensed_intent])
        except (json.JSONDecodeError, KeyError):
            # Fallback to the condensed intent as the query
            return [context.condensed_intent]
    
    async def _execute_research(
        self,
        context: WorkflowContext,
        queries: List[str],
    ) -> Dict[str, Any]:
        """Execute research using websearch agent.
        
        Uses Perplexity (via websearch agent) for deep research capabilities.
        """
        # Get websearch agent config
        try:
            websearch_config = self.get_agent_config("websearch")
        except FileNotFoundError:
            # Fallback config
            websearch_config = {
                "model": "perplexity/sonar-deep-research",
                "system_prompt": "You are a research agent. Search for current, accurate information.",
            }
        
        model = websearch_config.get("model", "perplexity/sonar-deep-research")
        system_prompt = websearch_config.get("system_prompt", "")
        
        # Build research prompt
        research_prompt = f"""Research the following queries to find current, accurate information:

Queries:
{chr(10).join(f"- {q}" for q in queries)}

Original question: {context.condensed_intent}

Provide:
1. Key findings with sources
2. Date/recency of information where available
3. Any conflicting information found
4. Confidence level in the findings

Format your response with clear sections for each query."""
        
        invocation = AgentInvocation(
            agent_name="websearch",
            model=model,
            system_prompt=system_prompt,
            user_prompt=research_prompt,
        )
        
        research_response = await self.call_agent(invocation)
        
        # Parse research results (simplified - actual implementation would extract structured data)
        return {
            "queries": queries,
            "response": research_response,
            "sources": self._extract_sources(research_response),
            "summary": research_response[:500] + "..." if len(research_response) > 500 else research_response,
        }
    
    def _extract_sources(self, response: str) -> List[Dict[str, str]]:
        """Extract sources from research response.
        
        This is a simplified extraction - in production would use
        more sophisticated parsing.
        """
        import re
        
        sources = []
        
        # Look for markdown links
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        matches = re.findall(link_pattern, response)
        
        for title, url in matches:
            if url.startswith("http"):
                sources.append({"title": title, "url": url})
        
        # Look for plain URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, response)
        
        existing_urls = {s["url"] for s in sources}
        for url in urls:
            if url not in existing_urls:
                sources.append({"title": url[:50], "url": url})
        
        return sources[:10]  # Limit to 10 sources
    
    def _summarize_research(self, research_results: Dict[str, Any]) -> str:
        """Create a summary of research results for user review."""
        summary = f"Found information for {len(research_results.get('queries', []))} queries.\n\n"
        
        if research_results.get("response"):
            # Extract first paragraph or so
            response = research_results["response"]
            if len(response) > 500:
                summary += response[:500] + "..."
            else:
                summary += response
        
        return summary
