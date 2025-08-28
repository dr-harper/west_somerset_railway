# West Somerset Railway Planning App - Product Requirements Document

## Executive Summary

A modern web application for the West Somerset Railway that provides passengers with easy access to train departure times and journey planning, combining contemporary usability with heritage-inspired design elements that honor the railway's 200+ year history.

## Product Vision

Create an intuitive, accessible railway planning application that serves both tourists and regular passengers of the West Somerset Railway, making it effortless to view departure boards, plan journeys, and explore the historic railway line.

## Core Features

### Phase 1: MVP (Departure Board)

#### 1. Station Departure Board
- **Primary Feature**: Real-time departure board display for any selected station
- **Key Functionality**:
  - Station selector dropdown with all WSR stations
  - Date picker for viewing different days' timetables
  - Live departure times showing next 5-10 trains
  - Train type indicators (Diesel, DMU, Steam)
  - Platform information (if applicable)
  - Service status indicators
  - Destination display
  - Journey duration estimates

#### 2. Station List
Complete list of stations on the line:
- Bishops Lydeard
- Crowcombe Heathfield
- Stogumber
- Williton
- Doniford Halt (Request stop)
- Watchet
- Washford
- Blue Anchor
- Dunster
- Minehead

### Phase 2: Enhanced Features

#### 3. Journey Planner
- Origin and destination selection
- Journey time calculator
- Connection information
- Return journey options
- Fare information integration

#### 4. Service Information
- Special event trains
- Heritage steam days
- Dining train services
- Seasonal timetable variations
- Engineering works notifications

#### 5. Interactive Route Map
- Visual representation of the railway line
- Station markers with quick access to departures
- Points of interest along the route
- Walking times between stations

### Phase 3: Advanced Features

#### 6. Accessibility Features
- Screen reader optimization
- High contrast mode
- Large text options
- Audio announcements
- Multi-language support

#### 7. Tourist Information
- Nearby attractions at each station
- Walking routes and trails
- Local amenities (cafes, toilets, parking)
- Photo galleries
- Historical information about stations

#### 8. Booking Integration
- Ticket purchasing (future API integration)
- Seat reservations for special services
- Group booking capabilities

## User Stories

### Primary User: Tourist/Visitor
"As a tourist visiting the West Somerset Railway, I want to quickly check when the next train departs from my current station so I can plan my day."

### Secondary User: Regular Passenger
"As a regular passenger, I want to check the timetable for my daily commute and receive updates about service changes."

### Tertiary User: Railway Enthusiast
"As a railway enthusiast, I want to see detailed information about special steam services and heritage events."

## Technical Architecture

### Frontend Stack
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite 5+
- **Styling**: 
  - CSS Modules for component styling
  - CSS Variables for theming
  - Optional: Tailwind CSS for utility classes
- **State Management**: 
  - React Context for global state
  - React Query/TanStack Query for API state
- **Routing**: React Router v6
- **Date Handling**: date-fns or dayjs
- **Testing**: Vitest + React Testing Library

### Component Structure
```
src/
├── components/
│   ├── DepartureBoard/
│   │   ├── DepartureBoard.tsx
│   │   ├── DepartureRow.tsx
│   │   ├── DepartureBoard.module.css
│   │   └── index.ts
│   ├── StationSelector/
│   ├── DatePicker/
│   ├── Layout/
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   └── Navigation.tsx
│   └── common/
│       ├── Button/
│       ├── Card/
│       └── Loading/
├── hooks/
│   ├── useTrainData.ts
│   └── useStation.ts
├── services/
│   ├── api.ts
│   └── mockData.ts
├── types/
│   ├── train.ts
│   └── station.ts
├── utils/
│   ├── dateHelpers.ts
│   └── formatters.ts
└── styles/
    ├── variables.css
    ├── global.css
    └── themes.css
```

### Data Structure
```typescript
interface Train {
  id: string;
  departureTime: string;
  arrivalTime?: string;
  destination: string;
  origin: string;
  serviceType: 'Diesel' | 'DMU' | 'Steam';
  platform?: string;
  status: 'On Time' | 'Delayed' | 'Cancelled';
  delay?: number;
  stops: Station[];
  isRequestStop?: boolean;
}

interface Station {
  id: string;
  name: string;
  code: string;
  coordinates?: {
    lat: number;
    lng: number;
  };
  facilities?: string[];
  isRequestStop?: boolean;
}

interface Departure {
  train: Train;
  station: Station;
  scheduledTime: string;
  expectedTime: string;
  platform?: string;
}
```

## Design System

### Visual Identity
- **Heritage Elements**:
  - British Rail-inspired typography (Johnston or similar)
  - Traditional railway color palette:
    - Deep burgundy (#6B1F2E)
    - Railway green (#2A4D3A)
    - Cream (#FFF8E7)
    - Cast iron black (#1C1C1C)
    - Brass/gold accents (#B8860B)
  
### UI Components Style Guide

#### Typography
- **Headers**: Serif font reminiscent of vintage railway posters (Playfair Display)
- **Body**: Clean sans-serif for readability (Inter, Roboto)
- **Departure Board**: Monospace for times (JetBrains Mono)

#### Visual Motifs
- Rounded corners mimicking vintage ticket windows
- Subtle drop shadows suggesting cast iron signage
- Border decorations inspired by Victorian ironwork
- Background patterns using railway track elements

#### Departure Board Design
- Split-flap display animation effects
- High contrast black background with amber/white text
- Clear hierarchy: Time > Destination > Platform > Status
- Visual indicators for service types (icons/badges)

### Responsive Design
- **Mobile First**: 320px minimum width
- **Breakpoints**:
  - Mobile: 320px - 767px
  - Tablet: 768px - 1023px
  - Desktop: 1024px+
- **Touch targets**: Minimum 44x44px
- **Gesture support**: Swipe between days, pull to refresh

## Mock Data Implementation

### Sample Timetable Data
Based on the provided timetable image, create mock data for:
- Northbound services (Bishops Lydeard to Minehead)
- Southbound services (Minehead to Bishops Lydeard)
- Multiple service types throughout the day
- Typical journey patterns

### API Structure (Future)
```typescript
// Future API endpoints
GET /api/departures/:stationId?date=YYYY-MM-DD
GET /api/stations
GET /api/journey/:from/:to?date=YYYY-MM-DD
GET /api/service/:trainId
GET /api/disruptions
```

## Performance Requirements
- **Initial Load**: < 3 seconds on 3G
- **Time to Interactive**: < 5 seconds
- **Lighthouse Score**: > 90 for Performance
- **Offline Support**: Cache last viewed timetable
- **PWA Ready**: Installable with offline functionality

## Accessibility Requirements
- WCAG 2.1 AA compliance
- Keyboard navigation support
- Screen reader announcements for departures
- Focus management
- Color contrast ratios meeting standards
- Alternative text for all images

## Browser Support
- Chrome/Edge (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Mobile Safari (iOS 12+)
- Chrome Mobile (Android 8+)

## Success Metrics
- User engagement: 70% daily active users checking departures
- Performance: 95% of page loads under 3 seconds
- Accessibility: Zero critical WCAG violations
- User satisfaction: 4.5+ star rating

## Development Phases

### Phase 1: MVP (Weeks 1-4)
- Basic departure board functionality
- Station selector
- Date navigation
- Mock data integration
- Responsive design
- Heritage theme implementation

### Phase 2: Enhanced Features (Weeks 5-8)
- Journey planner
- Service status updates
- Interactive map
- PWA implementation
- Performance optimization

### Phase 3: API Integration (Weeks 9-12)
- Replace mock data with real API
- Real-time updates
- Push notifications
- Advanced filtering
- User preferences

## Risk Mitigation
- **Data Accuracy**: Implement data validation and fallback to cached data
- **Performance**: Use lazy loading and code splitting
- **Browser Compatibility**: Progressive enhancement approach
- **Accessibility**: Regular audits during development

## Future Considerations
- Native mobile apps (React Native)
- Integration with National Rail systems
- QR code ticket scanning
- AR features for station navigation
- Social features for railway enthusiasts
- Multi-language support for international tourists

## Conclusion
This PRD outlines a comprehensive approach to building a modern yet heritage-inspired railway planning application for the West Somerset Railway. The phased approach allows for rapid MVP delivery while maintaining a clear path to a fully-featured application that serves all user groups effectively.