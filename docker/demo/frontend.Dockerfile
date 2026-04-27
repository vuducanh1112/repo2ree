FROM node:22-bookworm-slim

WORKDIR /app
RUN chown node:node /app

USER node

COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY --chown=node:node frontend ./

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
