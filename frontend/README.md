# Frontend - Telco Product Recommender UI

React-based user interface for displaying personalized telco product recommendations.

## Overview

Modern, responsive web application built with vanilla React (not Next.js) featuring:
- Personalized product recommendation cards
- Real-time event tracking (view, click, subscribe)
- A/B testing variant display
- Admin dashboard for metrics monitoring

## Technology Stack

- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **State Management**: Context API

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── components/      # Reusable UI components
│   ├── pages/          # Page-level components
│   ├── services/       # API integration layer
│   ├── context/        # Global state management
│   ├── hooks/          # Custom React hooks
│   ├── utils/          # Helper functions
│   ├── App.jsx         # Root component
│   └── index.jsx       # Application entry point
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## Setup Instructions

### Prerequisites
- Node.js 18+ and npm/yarn

### Installation

1. **Install dependencies**:
   ```bash
   npm install
   # or
   yarn install
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with backend API URL
   ```

3. **Start development server**:
   ```bash
   npm run dev
   # or
   yarn dev
   ```

   Access at: http://localhost:5173

## Development

### Building for Production
```bash
npm run build
npm run preview  # Preview production build
```

### Code Quality
```bash
# Lint
npm run lint

# Format
npm run format
```

## Key Components

### RecommendationCard
Displays individual product recommendation with:
- Product name, price, quota
- AI-generated recommendation reason (SHAP)
- CTA button (Activate Now)
- A/B variant indicator

### Dashboard
Admin monitoring interface showing:
- Real-time metrics (CTR, conversion rate)
- Latency performance (p95)
- A/B test results
- Feature importance charts

### Event Tracking
Automatic tracking of user interactions:
- `view`: Card appears in viewport
- `click`: User clicks CTA button
- `subscribe`: Product activation confirmed

## API Integration

All API calls go through `src/services/api.js`:
```javascript
// Example
import { getRecommendations } from './services/recommendationService';

const recs = await getRecommendations(userId, { limit: 5 });
```

Endpoints consumed:
- `POST /api/v1/recommend` - Get recommendations
- `POST /api/v1/events` - Track user events
- `GET /api/v1/products` - Product catalog
- `GET /api/v1/users/{id}` - User profile

## Styling Guidelines

Using Tailwind CSS utility-first approach:
- Mobile-first responsive design
- Consistent spacing (4px grid)
- Accessible color contrast (WCAG AA)
- Dark mode support (future)

## Performance Targets

| Metric | Target |
|--------|--------|
| First Contentful Paint | <1.5s |
| Time to Interactive | <3s |
| Bundle Size (initial) | <500KB |
| Lighthouse Score | >90 |

## Browser Support

- Chrome/Edge (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Mobile browsers (iOS Safari, Chrome Android)

## Status

🚧 **Under Development** - Sprint 3-5 implementation in progress

Waiting for:
- [ ] UI/UX design mockups
- [ ] Backend API availability
- [ ] Component library decisions

See `../IMPLEMENTATION_FLOW.md` for detailed implementation roadmap.
