import { useEffect, useRef, useCallback } from 'react';
import { useProposalsStore } from '../store/proposalsStore';

interface WebSocketMessage {
  type: 'plan_generating' | 'plan_ready' | 'plan_failed';
  sk: string;
  plan?: string;
  error?: string;
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const updateProposalInList = useProposalsStore((s) => s.updateProposalInList);
  const selectedProposal = useProposalsStore((s) => s.selectedProposal);
  const setSelectedProposal = useProposalsStore((s) => s.setSelectedProposal);

  const connect = useCallback(() => {
    const wsUrl = import.meta.env.VITE_API_URL?.replace(/^http/, 'ws') || 'ws://localhost:3004';
    const ws = new WebSocket(`${wsUrl}/ws`);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting in 3s...');
      setTimeout(connect, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;
  }, []);

  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      const { type, sk, plan, error } = message;

      if (type === 'plan_ready' && plan) {
        // Update the proposal in the list with the new plan
        updateProposalInList({
          ...selectedProposal!,
          sk,
          implementation_plan: plan,
        } as any);

        // Update selected proposal if it matches
        if (selectedProposal?.sk === sk) {
          setSelectedProposal({
            ...selectedProposal,
            implementation_plan: plan,
          });
        }
      } else if (type === 'plan_failed') {
        console.error('Plan generation failed:', error);
      }
    },
    [updateProposalInList, selectedProposal, setSelectedProposal]
  );

  useEffect(() => {
    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return wsRef.current;
}
