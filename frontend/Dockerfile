FROM node:22-slim AS build

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

# Build the project
RUN npm run build

# Use a second stage for a smaller image
FROM node:22-slim AS runtime

WORKDIR /app

# Copy built assets and necessary files
COPY --from=build /app/dist ./dist
COPY --from=build /app/package*.json ./
COPY --from=build /app/node_modules ./node_modules

# Set environment variables for runtime
ENV HOST=0.0.0.0
ENV PORT=4321
ENV VITE_API_BASE_URL=http://localhost:8000

EXPOSE 4321

# Run astro preview
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4321"]
