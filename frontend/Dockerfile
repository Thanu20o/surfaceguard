FROM node:20-alpine
WORKDIR /app
COPY package.json ./package.json
RUN npm install
COPY index.html vite.config.ts tsconfig.json tailwind.config.js postcss.config.js ./
COPY src ./src
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]