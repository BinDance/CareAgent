FROM node:20-alpine

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

COPY package.json /app/package.json
COPY pnpm-workspace.yaml /app/pnpm-workspace.yaml
COPY packages/shared-types/package.json /app/packages/shared-types/package.json
COPY packages/ui/package.json /app/packages/ui/package.json
COPY apps/elder-web/package.json /app/apps/elder-web/package.json
COPY apps/family-web/package.json /app/apps/family-web/package.json

RUN npm install

COPY packages/shared-types/src /app/packages/shared-types/src
COPY packages/ui/src /app/packages/ui/src
COPY apps/elder-web /app/apps/elder-web
COPY apps/family-web /app/apps/family-web

RUN npm run build -w apps/elder-web

EXPOSE 3000
CMD ["npm", "run", "start", "-w", "apps/elder-web"]
