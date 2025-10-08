# Google Ads Integration Setup Guide

## 🎯 **Simplified Setup - Reuses Existing Google OAuth**

The Google Ads integration now reuses your existing Google OAuth setup, so no additional configuration is needed!

## 📋 **Required Environment Variables**

Add these to your `.env` file (same as Google Analytics):

```bash
# Google OAuth (same as Google Analytics)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Encryption key for token storage
SECRET_KEY=your-secret-key-here
# SECRET_KEY=your_32_character_secret_key_here

# Optional: Google Ads Developer Token (only if you want to use Google Ads API)
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here
```

## 🔧 **Google Console Configuration**

### 1. **OAuth Scopes** (Add to existing OAuth app)
In your Google Cloud Console OAuth app, add these scopes:
- `https://www.googleapis.com/auth/adwords`
- `https://www.googleapis.com/auth/adsdatahub`

### 2. **Redirect URIs** (Same as Google Analytics)
- `https://localhost:3000/api/auth/callback/google` (development)
- `https://yourdomain.com/api/auth/callback/google` (production)

## 🚀 **How It Works**

1. **Single OAuth Flow**: Users connect via Google Analytics OAuth
2. **Automatic Scopes**: OAuth requests both Analytics AND Ads scopes
3. **Dual Connections**: Creates both Analytics and Ads connections automatically
4. **CrewAI Access**: Agents can access both Analytics and Ads data

## ✅ **Testing**

1. **Start the server**:
   ```bash
   cd SatoApp
   source ../venv/bin/activate
   uvicorn app.main:app --reload
   ```

2. **Test the frontend**:
   - Go to `https://localhost:3000`
   - Click "Connect Google Ads Account"
   - Complete OAuth flow
   - Both Analytics and Ads connections will be created

3. **Test CrewAI integration**:
   - Agents can now access Google Ads data using the `Google_Ads_Tool`
   - Data fetching works through the existing OAuth tokens

## 🎉 **Benefits**

- ✅ **No additional OAuth setup needed**
- ✅ **Reuses existing Google Console configuration**
- ✅ **Single OAuth flow for both services**
- ✅ **Automatic token management**
- ✅ **Seamless user experience**

## 🔍 **Troubleshooting**

### Server won't start?
- Make sure `SECRET_KEY` is set in your `.env` file
- The key must be exactly 32 characters long

### OAuth fails?
- Check that the Google Ads scopes are added to your OAuth app
- Verify redirect URIs are correct

### No Google Ads data?
- Ensure the OAuth flow completed successfully
- Check that both Analytics and Ads connections were created
- Verify the user has access to Google Ads accounts

## 📚 **Next Steps**

1. Add the Google Ads scopes to your Google Console OAuth app
2. Set the environment variables in your `.env` file
3. Deploy with `./deploy-fast.sh`
4. Test the integration!

The Google Ads integration is now seamlessly integrated with your existing Google Analytics setup! 🎯
