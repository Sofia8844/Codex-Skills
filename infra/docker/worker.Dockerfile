#  Se creo la imagen multiustage, Creacion etapa builder
FROM node:22-alpine AS builder

WORKDIR /usr/src/app 

COPY package*.json ./
RUN npm install

COPY tsconfig.json ./
COPY src ./src
COPY skills ./skills
COPY generar_ppt.js ./generar_ppt.js
COPY generar_ppt_codex.js ./generar_ppt_codex.js
COPY scripts ./scripts
COPY .codex ./.codex

RUN npm run build
#Creacion etapa RUNNER
FROM node:22-alpine AS runner

WORKDIR /usr/src/app
ENV NODE_ENV=production

COPY package*.json ./
RUN npm install --omit=dev
RUN npm install -g @openai/codex@0.116.0

COPY --from=builder /usr/src/app/dist ./dist
COPY --from=builder /usr/src/app/skills ./skills
COPY --from=builder /usr/src/app/generar_ppt.js ./generar_ppt.js
COPY --from=builder /usr/src/app/generar_ppt_codex.js ./generar_ppt_codex.js
COPY --from=builder /usr/src/app/scripts ./scripts
COPY --from=builder /usr/src/app/.codex ./.codex
# 
CMD ["node", "dist/apps/skill-worker/index.js"]
