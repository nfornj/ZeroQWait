# Build stage
FROM node:18-alpine AS build

WORKDIR /app

# Accept build argument for API URL with production default
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL

# Copy package files
COPY package*.json .npmrc ./

# Set memory limit for node process to avoid OOM
ENV NODE_OPTIONS="--max-old-space-size=4096"
ENV GENERATE_SOURCEMAP=false
ENV DISABLE_ESLINT_PLUGIN=true

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Patch react-scripts to fix OOM in ForkTsCheckerWebpackPlugin
RUN sed -i "s/mode: 'write-references',/mode: 'write-references', memoryLimit: 2048,/" node_modules/react-scripts/config/webpack.config.js
RUN sed -i "s/useTypeScript &&/false \&\&/g" node_modules/react-scripts/config/webpack.config.js

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Keep production/K8s defaults, while allowing Docker Compose to build an image
# that proxies to the local backend service and resolver.
ARG API_PROXY_TARGET=http://backend.zeroqwait.svc.cluster.local:8000
ARG API_DNS_RESOLVER=10.43.0.10

# Copy built assets from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i "s#__API_PROXY_TARGET__#${API_PROXY_TARGET}#g" /etc/nginx/conf.d/default.conf \
    && sed -i "s#__API_DNS_RESOLVER__#${API_DNS_RESOLVER}#g" /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
