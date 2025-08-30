# Firebase Backend Setup Guide for West Somerset Railway

## Overview
This guide outlines the complete setup process for adding a Firebase backend to the West Somerset Railway timetable application, including authentication and admin data management capabilities.

## Prerequisites
- Google Cloud Platform account
- Firebase project (free tier is sufficient for starting)
- Node.js and npm installed locally

## Firebase Console Setup

### 1. Create Firebase Project
1. Navigate to [Firebase Console](https://console.firebase.google.com)
2. Click "Create Project"
3. Project name: `west-somerset-railway`
4. Enable/disable Google Analytics based on preference
5. Wait for project provisioning

### 2. Enable Authentication
1. In Firebase Console, go to **Authentication** → **Get Started**
2. Navigate to **Sign-in method** tab
3. Enable the following providers:
   - **Email/Password** - For admin accounts
   - **Google** (optional) - For easier admin access
4. Navigate to **Users** tab
5. Add initial admin users manually:
   - Click "Add user"
   - Enter admin email and password
   - Record these credentials securely

### 3. Setup Firestore Database
1. Go to **Firestore Database** → **Create Database**
2. Choose **Production mode** for security
3. Select closest region (e.g., `europe-west2` for UK)
4. Initial collections structure:

```
firestore-root/
├── timetables/
│   ├── stations/
│   │   └── {stationId}/
│   │       ├── name: string
│   │       ├── code: string
│   │       ├── location: geopoint
│   │       └── facilities: array
│   ├── departures/
│   │   └── {departureId}/
│   │       ├── stationId: string
│   │       ├── destination: string
│   │       ├── scheduledTime: timestamp
│   │       ├── platform: string
│   │       ├── status: string
│   │       └── trainType: string
│   └── specialEvents/
│       └── {eventId}/
│           ├── date: timestamp
│           ├── description: string
│           └── affectedServices: array
├── users/
│   └── {userId}/
│       ├── email: string
│       ├── isAdmin: boolean
│       ├── createdAt: timestamp
│       └── lastLogin: timestamp
└── config/
    └── settings/
        ├── maintenanceMode: boolean
        ├── announcement: string
        └── lastUpdated: timestamp
```

### 4. Configure Security Rules
1. Go to **Firestore Database** → **Rules**
2. Replace default rules with:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Helper function to check if user is admin
    function isAdmin() {
      return request.auth != null && 
        get(/databases/$(database)/documents/users/$(request.auth.uid)).data.isAdmin == true;
    }
    
    // Public read access to timetables
    match /timetables/{document=**} {
      allow read: if true;
      allow write: if isAdmin();
    }
    
    // Config is readable by all, writable by admins
    match /config/{document=**} {
      allow read: if true;
      allow write: if isAdmin();
    }
    
    // Users can read their own profile, admins can read/write all
    match /users/{userId} {
      allow read: if request.auth != null && 
        (request.auth.uid == userId || isAdmin());
      allow write: if isAdmin();
    }
  }
}
```

3. Click **Publish** to activate rules

### 5. Get Firebase Configuration
1. Go to **Project Settings** (gear icon)
2. Scroll to **Your apps** section
3. Click **Web** icon (</>) to add web app
4. App nickname: `wsr-railway-web`
5. Check "Also set up Firebase Hosting" (optional)
6. Click **Register app**
7. Copy the configuration object:

```javascript
const firebaseConfig = {
  apiKey: "AIza...",
  authDomain: "west-somerset-railway.firebaseapp.com",
  projectId: "west-somerset-railway",
  storageBucket: "west-somerset-railway.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abc123def456"
};
```

## Local Development Setup

### 1. Environment Variables
Create `.env.local` in `app/wsr-railway-app/`:

```env
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_auth_domain
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_storage_bucket
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id

# Admin access configuration
VITE_ADMIN_ROUTE=/admin
VITE_ENABLE_KEYBOARD_SHORTCUT=true
```

### 2. Install Dependencies
```bash
cd app/wsr-railway-app
npm install firebase react-router-dom
```

### 3. Project Structure
```
src/
├── lib/
│   └── firebase/
│       ├── config.ts          # Firebase initialization
│       ├── auth.ts            # Authentication functions
│       └── firestore.ts       # Database operations
├── contexts/
│   └── AuthContext.tsx        # Auth state management
├── hooks/
│   ├── useAuth.ts             # Auth hook
│   └── useFirestore.ts        # Firestore data hook
├── components/
│   ├── Admin/
│   │   ├── AdminLogin.tsx     # Login form
│   │   ├── AdminDashboard.tsx # Main admin panel
│   │   ├── TimetableEditor.tsx
│   │   └── ProtectedRoute.tsx # Route guard
│   └── ...existing components
└── services/
    ├── adminService.ts         # Admin CRUD operations
    └── timetableService.ts     # Public data fetching
```

## Implementation Checklist

### Phase 1: Basic Setup ✓
- [ ] Create Firebase project
- [ ] Configure authentication
- [ ] Setup Firestore database
- [ ] Configure security rules
- [ ] Add environment variables
- [ ] Install dependencies

### Phase 2: Authentication
- [ ] Create Firebase configuration module
- [ ] Implement AuthContext provider
- [ ] Create login component
- [ ] Add logout functionality
- [ ] Implement session persistence
- [ ] Add password reset flow

### Phase 3: Admin Interface
- [ ] Create hidden admin route
- [ ] Implement ProtectedRoute component
- [ ] Build admin dashboard
- [ ] Add keyboard shortcut (Ctrl+Shift+A)
- [ ] Create admin navigation
- [ ] Add role-based access control

### Phase 4: Data Management
- [ ] Create timetable editor
- [ ] Implement station manager
- [ ] Add departure CRUD operations
- [ ] Build special events manager
- [ ] Create bulk import/export
- [ ] Add data validation

### Phase 5: Production Features
- [ ] Implement audit logging
- [ ] Add error tracking
- [ ] Create backup system
- [ ] Setup monitoring alerts
- [ ] Add rate limiting
- [ ] Implement caching strategy

## Security Best Practices

### 1. Environment Security
- Never commit `.env` files
- Use `.gitignore` for sensitive files
- Rotate API keys regularly
- Use different keys for dev/prod

### 2. Authentication Security
- Enforce strong passwords
- Implement session timeouts
- Add 2FA for admin accounts (optional)
- Log authentication attempts
- Monitor for suspicious activity

### 3. Database Security
- Validate all inputs
- Sanitize data before storage
- Use Firestore security rules
- Implement field-level validation
- Regular security audits

### 4. Admin Access Patterns

#### Option 1: Hidden URL
```javascript
// Access via /admin or custom route
<Route path="/admin" element={<ProtectedRoute><AdminDashboard /></ProtectedRoute>} />
```

#### Option 2: Keyboard Shortcut
```javascript
// Ctrl+Shift+A to show login modal
useEffect(() => {
  const handleKeyPress = (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'A') {
      setShowAdminLogin(true);
    }
  };
  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

#### Option 3: URL Parameter
```javascript
// Access via ?admin=true
const params = new URLSearchParams(location.search);
if (params.get('admin') === 'true') {
  // Show admin login
}
```

## Testing Strategy

### 1. Local Testing
- Use Firebase Emulators for local development
- Test with mock data
- Verify security rules locally

### 2. Staging Environment
- Create separate Firebase project for staging
- Mirror production configuration
- Test with real data subset

### 3. Production Deployment
- Progressive rollout
- Monitor error rates
- Have rollback plan ready

## Monitoring and Maintenance

### 1. Firebase Console Monitoring
- Check Authentication usage
- Monitor Firestore reads/writes
- Review security rules denials
- Track performance metrics

### 2. Error Tracking
- Implement error boundary in React
- Log errors to Firebase Analytics
- Set up alerts for critical errors

### 3. Regular Maintenance
- Weekly backup of Firestore data
- Monthly security rule review
- Quarterly dependency updates
- Annual security audit

## Cost Considerations

### Firebase Free Tier Limits
- Authentication: 10K verifications/month
- Firestore: 50K reads, 20K writes, 20K deletes/day
- Storage: 1GB
- Bandwidth: 10GB/month

### Estimated Usage (Small-Medium Traffic)
- Monthly cost: £0-10
- Consider caching for frequently accessed data
- Implement pagination for large datasets
- Use Firebase Analytics for insights

## Troubleshooting

### Common Issues

1. **CORS Errors**
   - Add domain to Firebase authorized domains
   - Check Firebase project settings

2. **Permission Denied**
   - Verify security rules
   - Check user authentication status
   - Ensure admin flag is set

3. **Data Not Updating**
   - Check network connectivity
   - Verify Firestore rules allow writes
   - Check for console errors

4. **Login Issues**
   - Verify email/password provider enabled
   - Check user exists in Firebase Auth
   - Clear browser cache/cookies

## Support Resources

- [Firebase Documentation](https://firebase.google.com/docs)
- [Firebase Community](https://firebase.google.com/community)
- [Stack Overflow Firebase Tag](https://stackoverflow.com/questions/tagged/firebase)
- [Firebase YouTube Channel](https://www.youtube.com/firebase)

## Next Steps

1. Create Firebase project in console
2. Configure authentication and database
3. Share configuration with development team
4. Begin Phase 1 implementation
5. Test with sample data
6. Iterate based on requirements

---

*Last Updated: [Current Date]*
*Version: 1.0.0*