FROM node:20-alpine AS base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .


FROM base AS test

RUN npm run lint


FROM base AS build

RUN npm run build


FROM nginx:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]