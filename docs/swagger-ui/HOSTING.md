# Swagger UI Hosting

This directory contains Swagger UI static files for the Zapier Triggers API documentation.

## Local Development

To view the Swagger UI locally:

1. **Option 1: Simple HTTP Server**
   ```bash
   cd docs/swagger-ui
   python3 -m http.server 8080
   ```
   Then open http://localhost:8080 in your browser.

2. **Option 2: SAM Local**
   ```bash
   sam local start-api
   ```
   The Swagger UI can be accessed via the API Gateway endpoint.

## Production Hosting

### Option A: S3 + CloudFront (Recommended)

1. **Upload to S3:**
   ```bash
   aws s3 sync docs/swagger-ui/ s3://your-swagger-ui-bucket/ --acl public-read
   ```

2. **Configure CloudFront:**
   - Create CloudFront distribution pointing to S3 bucket
   - Enable HTTPS
   - Set up custom domain (optional)
   - Configure CORS headers if needed

3. **Update OpenAPI spec server URLs:**
   - Update `servers` section in `openapi.yaml` with CloudFront URL

### Option B: API Gateway Stage

1. **Deploy Swagger UI as static files:**
   - Upload `index.html` and `openapi.yaml` to S3
   - Create API Gateway stage with static file serving
   - Configure CORS headers

2. **Access via API Gateway URL:**
   - Swagger UI accessible at: `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/swagger-ui/`

## Configuration

The Swagger UI is configured with:
- **Deep linking**: Enabled (URLs update when navigating)
- **Layout**: Standalone (full-page layout)
- **Filter**: Enabled (search box)
- **Try it out**: Enabled by default
- **Validator**: Disabled (no online validation)

## Customization

To customize the Swagger UI appearance:
- Edit `index.html` styles in the `<style>` section
- Modify SwaggerUIBundle configuration in the `<script>` section
- See [Swagger UI documentation](https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/) for options

## OpenAPI Spec Location

The Swagger UI loads the OpenAPI spec from `./openapi.yaml` (relative to `index.html`).

Ensure `openapi.yaml` is in the same directory as `index.html` or update the `url` in the SwaggerUIBundle configuration.

