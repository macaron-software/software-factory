# CarpoolGo - Mobile Carpooling App

## 1. Project Overview
- **Project Name:** CarpoolGo
- **Type:** Cross-platform Mobile Application (React Native / Expo)
- **Core Functionality:** A carpooling app that connects drivers with passengers heading the same direction, enabling cost-sharing rides
- **Target Users:** Commuters looking to share rides and split costs

## 2. Technology Stack
- **Framework:** React Native with Expo SDK 52
- **Language:** TypeScript
- **Navigation:** Expo Router (file-based routing)
- **State Management:** React Context + useState
- **UI Components:** Custom components + React Native core

## 3. UI/UX Specification

### Color Palette
- **Primary:** `#2ECC71` (Green - eco-friendly)
- **Primary Dark:** `#27AE60`
- **Secondary:** `#3498DB` (Blue)
- **Background:** `#F8F9FA` (Light gray)
- **Card:** `#FFFFFF`
- **Text Primary:** `#2C3E50`
- **Text Secondary:** `#7F8C8D`
- **Error:** `#E74C3C`
- **Warning:** `#F39C12`

### Typography
- **Headings:** System default bold
- **Body:** System default regular

## 4. Core Features

### 4.1 Ride Search (Home)
- Search bar for origin/destination
- Date picker for travel date
- List of available rides matching criteria
- Filter by time, price, seats available

### 4.2 Create Ride
- Form to publish a new ride
- Fields: origin, destination, date, time, available seats, price per seat

### 4.3 Ride Details
- Show ride information
- Show driver profile
- Show passengers (if any)
- Book ride button

### 4.4 User Profile
- User name and avatar
- My rides (as driver)
- My bookings (as passenger)
- Rating display

## 5. File Structure
```
/carpoolgo
  /app
    (tabs)/_layout.tsx
    (tabs)/index.tsx       # Home/Search
    (tabs)/create.tsx      # Create Ride
    (tabs)/profile.tsx     # Profile
    ride/[id].tsx         # Ride Details
  /components
    RideCard.tsx
    SearchBar.tsx
    DatePicker.tsx
  /context
    RideContext.tsx
    UserContext.tsx
  /data
    mockData.ts
  /types
    index.ts
  App.tsx
  package.json
```
