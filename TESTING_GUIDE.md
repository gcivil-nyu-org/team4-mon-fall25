# WebSocket Match Feature - Testing Guide

## Quick Access Links

### Main Application
- **Home/Login**: http://localhost:8001/
- **Sign Up**: http://localhost:8001/signup/
- **Profile**: http://localhost:8001/profile/
- **Solo Recommendations**: http://localhost:8001/recommend/

### Group Features
- **Create Group**: Click "Create Group" button on profile page
- **Join Group**: Click "Join Group" button, enter group code
- **Group Lobby**: http://localhost:8001/group/<UUID>/
- **Group Deck (Swipe Cards)**: http://localhost:8001/groups/<CODE>/deck/

---

## Testing WebSocket Match Feature

### Prerequisites
1. Server running on http://localhost:8001
2. Two different user accounts

### Step-by-Step Test

#### Step 1: Create Two User Accounts
1. Open http://localhost:8001/signup/
2. Create User 1 (e.g., "test1")
3. Logout
4. Create User 2 (e.g., "test2")

#### Step 2: Create & Join Group
**In Tab 1 (User 1):**
1. Login as test1
2. Go to profile: http://localhost:8001/profile/
3. Click "Create Group"
4. Note the group code (e.g., "ABC123")
5. You'll be redirected to group lobby

**In Tab 2 (User 2):**
1. Login as test2  
2. Go to profile: http://localhost:8001/profile/
3. Click "Join Group"
4. Enter the same group code (e.g., "ABC123")
5. You'll be redirected to group lobby

#### Step 3: Start Swiping in Both Tabs
**In both Tab 1 and Tab 2:**
1. In the group lobby, click "▶️ Start Matching"
2. You'll go to `/groups/<CODE>/deck/`
3. Open browser console (F12)
4. Look for: `[WebSocket] Connection opened`

#### Step 4: Test Match Detection
**In Tab 1:**
1. Find a movie you both want to like
2. Swipe right (click Like button or drag right)
3. Movie disappears
4. Check console - no match yet (only 1 vote)

**In Tab 2:**
1. Find THE SAME movie
2. Swipe right on the same movie
3. 💥 **MATCH MODAL APPEARS AUTOMATICALLY!**
4. In Tab 1, you should also see the modal appear!

---

## Expected Console Output

### Tab 1 & Tab 2 (Both users)
```
[WebSocket] Connecting to ws://localhost:8001/ws/match/ABC123/
[WebSocket] Connection opened
[WebSocket] Received: {type: "connection_established", group_code: "ABC123"}
[WebSocket] Connected to group: ABC123
```

### When Match Happens
```
[WebSocket] Received: {type: "match_found", movie_title: "The Matrix", ...}
[WebSocket] Match found! {tmdb_id: 123, movie_title: "The Matrix", ...}
```

---

## Troubleshooting

### Issue: WebSocket connection fails
**Solution**: Check if server is running with ASGI (Daphne). Should see:
```
Starting ASGI/Daphne version 4.2.1 development server at http://127.0.0.1:8001/
```

### Issue: No match modal appears
**Solution**: 
1. Check browser console for errors
2. Verify both users are in the same group
3. Verify both liked the EXACT same movie (same tmdb_id)
4. Check if match was already created (won't trigger again)

### Issue: Modal appears but no movie details
**Solution**: Check TMDB API key in `.env` file. Without it, movie details won't load.

---

## What to Look For

✅ **Success Indicators:**
- WebSocket connects successfully
- Match modal appears on BOTH tabs simultaneously
- Modal shows movie poster, title, year, genres
- Auto-hides after 5 seconds

❌ **Common Issues:**
- "WebSocket connection failed" → Server not running with Daphne
- "Match modal doesn't appear" → Check if both users liked same movie
- "Console shows errors" → Check for CORS or authentication issues

---

## Quick Check Commands

```bash
# Check if server is running
netstat -ano | findstr :8001

# Check logs for WebSocket events
# Look for: [MatchConsumer] Connection accepted
# Look for: [WebSocket] Broadcast match event
```

---

## Next Steps After Testing

1. If working: Create more complex scenarios (3+ users)
2. If not working: Check console errors and fix
3. Optional: Add match history UI
4. Optional: Add sound effects on match

