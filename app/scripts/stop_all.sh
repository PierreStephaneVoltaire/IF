#!/bin/bash

# ============================================================
# IF Prototype A1 - Stop All Services Script
# ============================================================

echo "============================================================"
echo "        IF Prototype A1 - Stopping All Services"
echo "============================================================"
echo ""

echo "Stopping tsx processes..."
pkill -f "tsx" 2>/dev/null && echo "  ✓ Killed tsx processes" || echo "  - No tsx processes found"

echo "Stopping vite processes..."
pkill -f "vite" 2>/dev/null && echo "  ✓ Killed vite processes" || echo "  - No vite processes found"

echo "Stopping uvicorn processes..."
pkill -f "uvicorn" 2>/dev/null && echo "  ✓ Killed uvicorn processes" || echo "  - No uvicorn processes found"

echo "Stopping node processes on portal ports..."
for port in 3000 3001 3002 3003 3004 5173 5174 5175 5176 5177 5178 5179 5180 5181 5182; do
    if netstat -ano 2>/dev/null | grep -q ":$port "; then
        fuser -k $port/tcp 2>/dev/null && echo "  ✓ Killed process on port $port"
    fi
done

echo ""
echo "============================================================"
echo "              All Services Stopped!"
echo "============================================================"
