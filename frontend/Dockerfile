# ---- 构建阶段 ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# ---- 运行阶段：Nginx 托管静态资源并反代 API ----
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public/sample_wafer_data.csv /usr/share/nginx/html/sample_wafer_data.csv
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
