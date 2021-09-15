FROM node:14.3.0-alpine as build

WORKDIR /usr/src

# Copy the React app to the container
COPY . .

# Prepare the container for building React
RUN npm install --silent
RUN npm run build

# Prepare Nginx
FROM nginx:1.21-alpine
COPY --from=build /usr/src/build /usr/share/nginx/html
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/nginx.conf /etc/nginx/conf.d

# Fire up Nginx
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]