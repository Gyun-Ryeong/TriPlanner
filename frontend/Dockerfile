# 화면 (React). 1단계에서 빌드하고, 2단계 Nginx가 빌드 결과를 주면서 /api 는 백엔드로 넘긴다 (deploy/nginx.conf)
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
