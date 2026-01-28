# FastFlow Web Interface

This is the web frontend for the FastFlow application, built with Vue 3, TypeScript, and Vite. It provides a chat interface for generating workflow diagrams through interaction with the backend engine module.

## Features

- Chat interface for describing workflows
- Integration with backend engine module for workflow generation
- Real-time workflow diagram display
- Responsive design

## Project Setup

```bash
npm install
```

### Compile and Hot-Reload for Development

```bash
npm run dev
```

### Type-Check, Compile and Minify for Production

```bash
npm run build
```

## Project Structure

- `src/` - Main source code
  - `components/` - Vue components
  - `views/` - Page views
  - `router/` - Vue Router configuration
  - `services/` - Nexus services
- `public/` - Static assets

## Nexus Integration

The frontend communicates with the backend engine module through RESTful APIs. The Nexus calls are proxied through Vite's development server to avoid CORS issues.

## Development

To start the development server:

```bash
npm run dev
```

The application will be available at http://localhost:5173 by default.

## Building for Production

To create a production build:

```bash
npm run build
```

The built files will be output to the `dist` directory.
