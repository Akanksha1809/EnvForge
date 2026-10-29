# Three stages:
#  - builder: compiles the production static bundle, never shipped itself.
#  - dev: full node_modules + Vite's dev server, used only by
#    docker-compose.yml's `target: dev` for local hot-reload development.
#  - production (default target, last stage): nginx serving only the
#    compiled static files — no node_modules, no npm devDependencies, no
#    bundler binaries (e.g. esbuild, which Vite pulls in and which is
#    itself a compiled Go binary) ship in this image. This is the image
#    CI's container-scan actually scans, and the one a real deployment
#    would use — scanning the dev-mode image instead (as this project did
#    before this fix) means the CVE findings include an entire Go runtime
#    and a full dev-dependency tree that never reaches production.

FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

FROM nginx:1.29-alpine AS production
# The published nginx:alpine tag is only as fresh as whenever it was last
# built — Alpine's own package repo keeps shipping patched `apk` packages
# in between those builds. Pulling the latest ones at build time (rather
# than only whatever shipped with the base image) is the standard way to
# avoid shipping known-fixed CVEs that the base image just hasn't caught
# up to yet.
RUN apk update && apk upgrade --no-cache
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
