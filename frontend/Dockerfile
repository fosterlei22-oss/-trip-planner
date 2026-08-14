# ---- build stage：Node 构建生产产物 ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- serve stage：nginx 托管静态文件 ----
FROM nginx:alpine
# 端口与后端地址做成环境变量，启动时经官方镜像的 envsubst 模板机制注入：
# 本地 compose 用默认值（80 / backend:8000），Render 会覆盖成 $PORT 与后端私有网络地址。
# 注意 BACKEND_URL 是「host:port」裸地址，nginx 模板里会补上 http:// 前缀
ENV PORT=80
ENV BACKEND_URL=backend:8000
COPY --from=build /app/dist /usr/share/nginx/html
# 官方 nginx 镜像会把 /etc/nginx/templates/*.template 渲染成 /etc/nginx/conf.d/*.conf
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80
