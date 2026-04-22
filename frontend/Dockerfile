# Frontend Dockerfile - production-ready with security hardening

# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application (BASE_PATH defaults to / for root serving)
ARG BASE_PATH=/
ENV BASE_PATH=${BASE_PATH}
RUN npm run build

# Production stage - nginx:alpine drops privileges automatically
FROM nginx:alpine

# Copy built files to nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Health check for nginx
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
