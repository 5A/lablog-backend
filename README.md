# lablog-backend

Backend for `lablog`.
`lablog` is the software behind my blog https://zzi.io

## Dev Setup

1.  Setup python environment for FastAPI.

2.  In parent directory, run

        $ uvicorn backend.main:app --log-config backend/uvicorn_log.config.yaml --host 0.0.0.0

## Production Deployment

1.  Setup python environment for FastAPI

2.  In parent directory, run

        $ uvicorn backend.main:app --log-config backend/uvicorn_log.config.yaml

    This makes the uvicorn server to only listen to localhost access

3.  Setup reverse proxy for the uvicorn listening location at http://127.0.0.1:8000, to encrypt your connection with SSL.

    For nginx it looks like this (this is only for demostrating the idea, you probably need to use more proper ciphers and settings for TLS):

        listen 443 ssl;
        listen [::]:443 ssl;
        server_name blogapi.zzi.io;

        ssl_certificate       /etc/nginx/ssl/blogapi/cert.pem;
        ssl_certificate_key   /etc/nginx/ssl/blogapi/key.pem;

        location / { 
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

    The idea is to handle TLS with nginx, and inside the server it is still plain HTTP.
    This makes it easier for development, and offers better performance.
