FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_CATALOG_API_URL=/api/catalog/products/
ARG VITE_ALERTS_API_URL=/api/alerts/subscribe/

ENV VITE_CATALOG_API_URL=$VITE_CATALOG_API_URL
ENV VITE_ALERTS_API_URL=$VITE_ALERTS_API_URL

COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
