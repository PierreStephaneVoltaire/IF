#!/bin/bash

# ============================================================
# IF Prototype A1 - Start All Services Script
# ============================================================
# This script starts all backend and frontend services for the
# IF Prototype A1 system including the main Python backend and
# all portal applications.
# ============================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the app directory (parent of scripts folder)
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UTILS_DIR="$(cd "$APP_DIR/.." && pwd)/utils"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}       IF Prototype A1 - Starting All Services${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Array to store background process PIDs
declare -a PIDS=()
declare -a SERVICES=()

# Function to check if a port is in use
check_port() {
    local port=$1
    if netstat -ano 2>/dev/null | grep -q ":$port "; then
        return 0  # Port is in use
    fi
    return 1  # Port is free
}

# Function to wait for a service to be ready
wait_for_service() {
    local port=$1
    local name=$2
    local max_attempts=30
    local attempt=0

    echo -e "${YELLOW}Waiting for $name to be ready on port $port...${NC}"
    while ! check_port $port; do
        sleep 1
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            echo -e "${RED}Timeout waiting for $name to start${NC}"
            return 1
        fi
    done
    echo -e "${GREEN}$name is ready on port $port${NC}"
    return 0
}

# ============================================================
# 1. Start Main Python Backend (Port 8000)
# ============================================================
echo -e "${BLUE}[1/6] Starting Main Python Backend...${NC}"
cd "$APP_DIR"

# Activate virtual environment and start uvicorn
if [ -d "venv" ]; then
    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate 2>/dev/null
fi

# Run from src directory so relative imports work
cd "$APP_DIR/src"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
PIDS+=($!)
SERVICES+=("Main Backend (Python):8000")
echo -e "${GREEN}Started Main Python Backend on port 8000 (PID: ${PIDS[-1]})${NC}"

# ============================================================
# 2. Start Main Portal (Port 3000 backend, 5174 frontend)
# ============================================================
echo -e "${BLUE}[2/6] Starting Main Portal...${NC}"
cd "$UTILS_DIR/main-portal/backend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for main-portal backend...${NC}"
    npm install --silent
fi

npm run dev &
PIDS+=($!)
SERVICES+=("Main Portal Backend:3000")
echo -e "${GREEN}Started Main Portal Backend on port 3000 (PID: ${PIDS[-1]})${NC}"

cd "$UTILS_DIR/main-portal/frontend"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for main-portal frontend...${NC}"
    npm install --silent
fi

npm run dev -- --port 5174 &
PIDS+=($!)
SERVICES+=("Main Portal Frontend:5174")
echo -e "${GREEN}Started Main Portal Frontend on port 5174 (PID: ${PIDS[-1]})${NC}"

# ============================================================
# 3. Start Powerlifting App (Port 3001 backend, 5175 frontend)
# ============================================================
echo -e "${BLUE}[3/6] Starting Powerlifting App...${NC}"
cd "$UTILS_DIR/powerlifting-app/backend"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for powerlifting-app backend...${NC}"
    npm install --silent
fi

npm run dev &
PIDS+=($!)
SERVICES+=("Powerlifting Backend:3001")
echo -e "${GREEN}Started Powerlifting Backend on port 3001 (PID: ${PIDS[-1]})${NC}"

cd "$UTILS_DIR/powerlifting-app/frontend"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for powerlifting-app frontend...${NC}"
    npm install --silent
fi

npm run dev -- --port 5175 &
PIDS+=($!)
SERVICES+=("Powerlifting Frontend:5175")
echo -e "${GREEN}Started Powerlifting Frontend on port 5175 (PID: ${PIDS[-1]})${NC}"

# ============================================================
# 4. Start Finance Portal (Port 3002 backend, 5176 frontend)
# ============================================================
echo -e "${BLUE}[4/6] Starting Finance Portal...${NC}"
cd "$UTILS_DIR/finance-portal/backend"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for finance-portal backend...${NC}"
    npm install --silent
fi

npm run dev &
PIDS+=($!)
SERVICES+=("Finance Backend:3002")
echo -e "${GREEN}Started Finance Backend on port 3002 (PID: ${PIDS[-1]})${NC}"

cd "$UTILS_DIR/finance-portal/frontend"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for finance-portal frontend...${NC}"
    npm install --silent
fi

npm run dev -- --port 5176 &
PIDS+=($!)
SERVICES+=("Finance Frontend:5176")
echo -e "${GREEN}Started Finance Frontend on port 5176 (PID: ${PIDS[-1]})${NC}"

# ============================================================
# 5. Start Diary Portal (Port 3003 backend, 5177 frontend)
# ============================================================
echo -e "${BLUE}[5/6] Starting Diary Portal...${NC}"
cd "$UTILS_DIR/diary-portal/backend"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for diary-portal backend...${NC}"
    npm install --silent
fi

npm run dev &
PIDS+=($!)
SERVICES+=("Diary Backend:3003")
echo -e "${GREEN}Started Diary Backend on port 3003 (PID: ${PIDS[-1]})${NC}"

cd "$UTILS_DIR/diary-portal/frontend"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for diary-portal frontend...${NC}"
    npm install --silent
fi

npm run dev -- --port 5177 &
PIDS+=($!)
SERVICES+=("Diary Frontend:5177")
echo -e "${GREEN}Started Diary Frontend on port 5177 (PID: ${PIDS[-1]})${NC}"

# ============================================================
# 6. Start Proposals Portal (Port 3004 backend, 5178 frontend)
# ============================================================
echo -e "${BLUE}[6/6] Starting Proposals Portal...${NC}"
cd "$UTILS_DIR/proposals-portal/backend"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for proposals-portal backend...${NC}"
    npm install --silent
fi

npm run dev &
PIDS+=($!)
SERVICES+=("Proposals Backend:3004")
echo -e "${GREEN}Started Proposals Backend on port 3004 (PID: ${PIDS[-1]})${NC}"

cd "$UTILS_DIR/proposals-portal/frontend"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for proposals-portal frontend...${NC}"
    npm install --silent
fi

npm run dev -- --port 5178 &
PIDS+=($!)
SERVICES+=("Proposals Frontend:5178")
echo -e "${GREEN}Started Proposals Frontend on port 5178 (PID: ${PIDS[-1]})${NC}"

# ============================================================
# Summary
# ============================================================
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}              All Services Started!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${BLUE}Services running:${NC}"
echo ""
printf "  %-35s %s\n" "SERVICE" "PORT"
printf "  %-35s %s\n" "-------" "----"
printf "  %-35s ${GREEN}%s${NC}\n" "Main Python Backend" "8000"
printf "  %-35s ${GREEN}%s${NC}\n" "Main Portal Frontend" "5174"
printf "  %-35s ${GREEN}%s${NC}\n" "Powerlifting Frontend" "5175"
printf "  %-35s ${GREEN}%s${NC}\n" "Finance Frontend" "5176"
printf "  %-35s ${GREEN}%s${NC}\n" "Diary Frontend" "5177"
printf "  %-35s ${GREEN}%s${NC}\n" "Proposals Frontend" "5178"
echo ""
echo -e "${YELLOW}Backend APIs:${NC}"
printf "  %-35s ${GREEN}%s${NC}\n" "Main Portal Backend" "3000"
printf "  %-35s ${GREEN}%s${NC}\n" "Powerlifting Backend" "3001"
printf "  %-35s ${GREEN}%s${NC}\n" "Finance Backend" "3002"
printf "  %-35s ${GREEN}%s${NC}\n" "Diary Backend" "3003"
printf "  %-35s ${GREEN}%s${NC}\n" "Proposals Backend" "3004"
echo ""
echo -e "${BLUE}PIDs: ${PIDS[*]}${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Save PIDs to file for later cleanup
echo "${PIDS[*]}" > "$APP_DIR/.service_pids"

# Trap Ctrl+C to kill all background processes
trap 'echo ""; echo -e "${YELLOW}Stopping all services...${NC}"; for pid in ${PIDS[*]}; do kill $pid 2>/dev/null; done; rm -f "$APP_DIR/.service_pids"; echo -e "${GREEN}All services stopped.${NC}"; exit 0' SIGINT SIGTERM

# Wait for all background processes
wait
