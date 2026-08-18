# Build
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
ARG NPM_REGISTRY=
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npm ci
COPY . .
ARG VITE_ADMIN_TOKEN=
ARG VITE_BASE=/
ENV VITE_ADMIN_TOKEN=$VITE_ADMIN_TOKEN
ENV VITE_BASE=$VITE_BASE
RUN npm run build

# Serve
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
