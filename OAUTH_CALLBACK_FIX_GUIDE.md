# 🚨 OAuth Callback Errors Fix Guide

## **Issues Identified**

1. **Google OAuth**: `invalid_grant` error during token exchange
2. **Facebook OAuth**: `400 Bad Request` and "Could not get user email from Facebook"

## **Root Causes & Solutions**

### **1. Google OAuth `invalid_grant` Error**

#### **Common Causes:**
- Authorization code already used (codes can only be used once)
- Authorization code expired (usually 10 minutes)
- Redirect URI mismatch between OAuth request and callback
- Client ID/Secret mismatch

#### **Solutions:**

**A. Check Environment Variables**
```bash
# In SatoApp/.env file, ensure these are set:
GOOGLE_CLIENT_ID=your_actual_google_client_id
GOOGLE_CLIENT_SECRET=your_actual_google_client_secret
```

**B. Verify OAuth Console Configuration**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to: **APIs & Services** → **Credentials**
3. Click your OAuth 2.0 Client ID
4. **CRITICAL**: Ensure redirect URIs match exactly:
   - `https://sato-frontend-397762748853.me-west1.run.app/auth/ga-callback`
   - `https://localhost:3000/auth/ga-callback` (for local testing)

**C. Check for Multiple OAuth Attempts**
- OAuth codes can only be used once
- If user refreshes the callback page, it tries to use the same code again
- Solution: Implement proper redirect after successful callback

### **2. Facebook OAuth `400 Bad Request` Error**

#### **Common Causes:**
- App ID/Secret mismatch
- Redirect URI not whitelisted in Facebook Console
- Insufficient permissions for email access
- Facebook app not in production mode

#### **Solutions:**

**A. Check Environment Variables**
```bash
# In SatoApp/.env file, ensure these are set:
FACEBOOK_APP_ID=your_actual_facebook_app_id
FACEBOOK_APP_SECRET=your_actual_facebook_app_secret
```

**B. Verify Facebook Developer Console**
1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Select your app
3. Navigate to: **Facebook Login** → **Settings**
4. **CRITICAL**: Add these Valid OAuth Redirect URIs:
   - `https://sato-frontend-397762748853.me-west1.run.app/auth/facebook-callback`
   - `https://localhost:3000/auth/facebook-callback` (for local testing)

**C. Check App Permissions**
1. In Facebook Developer Console → **App Review** → **Permissions and Features**
2. Ensure `email` permission is approved or request it
3. For development, add test users with email access

**D. Facebook App Mode**
- Development apps have limited functionality
- Consider switching to Live mode for production
- Test users must be added in development mode

## **Enhanced Debug Information**

I've added comprehensive debug logging to both OAuth services. After deploying, check the backend logs for:

### **Google OAuth Debug Output:**
```
🔧 Google OAuth Debug:
  - Code: AQAAGKEsx...
  - Redirect URI: https://sato-frontend-397762748853.me-west1.run.app/auth/ga-callback
  - Client ID: 1234567890...
  - Client Secret: SET
  - Token exchange successful/failed: [details]
```

### **Facebook OAuth Debug Output:**
```
🔧 Facebook OAuth Debug:
  - Code: AQAAGKEsx...
  - Redirect URI: https://sato-frontend-397762748853.me-west1.run.app/auth/facebook-callback
  - App ID: 1234567890...
  - App Secret: SET
  - Response status: 200/400
  - Token data keys: [access_token, ...]
  - User info: {email: user@example.com}
```

## **Step-by-Step Fix Process**

### **Step 1: Update Backend with Debug Code**
```bash
cd SatoApp/
# Deploy with enhanced debug logging
./deploy-fast.sh
```

### **Step 2: Check Environment Variables**
Ensure your `.env` file has all required OAuth credentials:
```bash
# Check if variables are set
grep -E "(GOOGLE_CLIENT|FACEBOOK_APP)" .env
```

### **Step 3: Verify OAuth Provider Configuration**
- **Google Console**: Exact redirect URI match
- **Facebook Console**: Exact redirect URI match + email permission

### **Step 4: Test OAuth Flows**
1. **Clear browser cache/cookies**
2. **Try OAuth flow**
3. **Check backend logs** for debug output
4. **Check browser console** for frontend errors

### **Step 5: Analyze Debug Output**

#### **If Google OAuth fails:**
- Check if Client ID/Secret are loaded correctly
- Verify redirect URI matches exactly
- Ensure code hasn't been used before

#### **If Facebook OAuth fails:**
- Check HTTP status code (400 = bad request, 401 = unauthorized)
- Verify App ID/Secret are loaded correctly
- Check if email permission is granted

## **Common Configuration Mistakes**

### **Google Console:**
❌ **Wrong**: `https://sato-frontend-397762748853.me-west1.run.app/auth/ga-callback/`  
✅ **Correct**: `https://sato-frontend-397762748853.me-west1.run.app/auth/ga-callback`

### **Facebook Console:**
❌ **Wrong**: Missing `https://localhost:3000` origins for local testing  
✅ **Correct**: Include both production and local URLs

### **Environment Variables:**
❌ **Wrong**: Using development credentials in production  
✅ **Correct**: Separate credentials for dev/prod environments

## **Testing Checklist**

### **Before Testing:**
- [ ] Environment variables set correctly
- [ ] OAuth provider configuration updated
- [ ] Backend deployed with debug logging
- [ ] Frontend deployed with correct URLs

### **During Testing:**
- [ ] Clear browser cache/cookies
- [ ] Check browser console for errors
- [ ] Check backend logs for debug output
- [ ] Try both local and production environments

### **After Testing:**
- [ ] OAuth flows complete successfully
- [ ] User email retrieved correctly
- [ ] Connections saved to database
- [ ] No repeated code usage errors

## **Emergency Fallback**

If OAuth issues persist:

1. **Create new OAuth apps** in Google/Facebook consoles
2. **Use fresh credentials** in environment variables
3. **Test with minimal scopes** first (just email/profile)
4. **Add additional scopes** after basic OAuth works

## **Debug Commands**

### **Check Backend Logs:**
```bash
# For Google Cloud Run
gcloud logs read --service=sato-backend --limit=50

# Look for OAuth debug output
gcloud logs read --service=sato-backend --filter="🔧" --limit=20
```

### **Test OAuth URLs:**
```bash
# Test if OAuth URL generation works
curl "${NEXT_PUBLIC_API_URL}/api/v1/google-analytics/oauth-url?redirect_uri=https://sato-frontend-397762748853.me-west1.run.app/auth/ga-callback"
```

The enhanced debug logging will show you exactly what's happening during the OAuth process and help identify the specific issue! 🔍


