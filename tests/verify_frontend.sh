#!/bin/bash

echo "=== Sprint 3 Frontend Verification ==="
echo ""

# Check directory structure
echo "✓ Checking frontend structure..."
cd "/home/arielsulton/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone/frontend"

# Count files
COMPONENTS=$(find src/components -name "*.jsx" | wc -l)
PAGES=$(find src/pages -name "*.jsx" | wc -l)
SERVICES=$(find src/services -name "*.js" | wc -l)
CONTEXT=$(find src/context -name "*.jsx" | wc -l)
HOOKS=$(find src/hooks -name "*.js" | wc -l)

echo "  Components: $COMPONENTS/7"
echo "  Pages: $PAGES/9"
echo "  Services: $SERVICES/4"
echo "  Context: $CONTEXT/2"
echo "  Hooks: $HOOKS/2"
echo ""

# Check key files
echo "✓ Checking key files..."
[ -f "src/App.jsx" ] && echo "  App.jsx: ✓" || echo "  App.jsx: ✗"
[ -f "src/main.jsx" ] && echo "  main.jsx: ✓" || echo "  main.jsx: ✗"
[ -f "src/index.css" ] && echo "  index.css: ✓" || echo "  index.css: ✗"
[ -f "public/index.html" ] && echo "  index.html: ✓" || echo "  index.html: ✗"
[ -f ".env.example" ] && echo "  .env.example: ✓" || echo "  .env.example: ✗"
echo ""

# Check configuration
echo "✓ Checking configuration..."
[ -f "package.json" ] && echo "  package.json: ✓" || echo "  package.json: ✗"
[ -f "vite.config.js" ] && echo "  vite.config.js: ✓" || echo "  vite.config.js: ✗"
[ -f "tailwind.config.js" ] && echo "  tailwind.config.js: ✓" || echo "  tailwind.config.js: ✗"
echo ""

echo "=== Verification Complete ==="
echo ""
echo "To start development:"
echo "  cd frontend"
echo "  npm install"
echo "  npm run dev"
