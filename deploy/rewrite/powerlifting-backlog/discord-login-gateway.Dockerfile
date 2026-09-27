FROM node:20-alpine
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY backend/package.json backend/package.json
COPY frontend/package.json frontend/package.json
COPY packages/types/package.json packages/types/package.json
RUN npm ci --omit=dev
COPY backend/dist backend/dist
COPY packages/types packages/types
COPY services/operations services/operations
COPY services/calculation_constants.json services/calculation_constants.json
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001 -G nodejs && chown -R nodejs:nodejs /workspace/backend /workspace/packages /workspace/services
WORKDIR /workspace/backend
ENV NODE_ENV=production
EXPOSE 3005
USER nodejs
CMD ["node", "dist/server.js"]
