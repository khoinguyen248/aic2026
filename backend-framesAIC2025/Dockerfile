FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY server.js ./

ENV PORT=8080
ENV KEYFRAMES_PATH=/data/keyframes

EXPOSE 8080

CMD ["npm", "start"]
