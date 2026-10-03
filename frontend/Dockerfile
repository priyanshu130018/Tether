# ==============================================================================
# Tether Frontend - Production Multi-Stage Dockerfile
# ==============================================================================

# --- Stage 1: Build Frontend Assets ---
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- Stage 2: Hardened Nginx Web Server ---
FROM nginx:1.27-alpine AS production

# Set working directory to static HTML root
WORKDIR /usr/share/nginx/html

# Clean default assets and copy production build
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add non-root permissions for nginx cache and run directories
RUN touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid /var/cache/nginx /usr/share/nginx/html

# Expose standard HTTP port
EXPOSE 80

# Healthcheck testing root endpoint
HEALTHCHECK --interval=20s --timeout=3s --retries=3 \
    CMD wget -qO- http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
