# Deploying to Vercel

This guide will help you deploy your League Scheduler Next.js application to Vercel.

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub/GitLab/Bitbucket**: Your code should be in a Git repository
3. **Supabase Project**: Ensure your Supabase project is set up and accessible

## Step 1: Prepare Your Repository

Make sure your code is committed and pushed to your Git repository:

```bash
git add .
git commit -m "Prepare for Vercel deployment"
git push origin main
```

## Step 2: Deploy to Vercel

### Option A: Deploy via Vercel Dashboard (Recommended)

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "New Project"
3. Import your Git repository
4. Vercel will automatically detect it's a Next.js project
5. Configure your project settings:
   - **Framework Preset**: Next.js (should be auto-detected)
   - **Root Directory**: Leave as default (root of your repo)
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)
   - **Install Command**: `npm install` (auto-detected)

### Option B: Deploy via Vercel CLI

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Deploy:
   ```bash
   vercel
   ```

## Step 3: Configure Environment Variables

In your Vercel project dashboard, go to **Settings → Environment Variables** and add:

### Required Environment Variables:

```
NEXT_PUBLIC_SUPABASE_URL=https://zcoupiuradompbrsebdp.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpjb3VwaXVyYWRvbXBicnNlYmRwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY2MzQ3OTMsImV4cCI6MjA3MjIxMDc5M30.OaveieA8KkcWyMZr-H-0xwO6A38zjpGaFIJp3okfZlI
SUPABASE_SERVICE_ROLE_KEY=your_actual_service_role_key_here
```

### How to Get Your Service Role Key:

1. Go to your [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Go to **Settings → API**
4. Copy the **service_role** key (starts with `eyJ...`)
5. Paste it as the value for `SUPABASE_SERVICE_ROLE_KEY`

## Step 4: Configure Supabase for Production

### 1. Update RLS Policies (if needed)

Ensure your Supabase Row Level Security policies allow access from Vercel's IP ranges.

### 2. Check Database Connection

Verify your database is accessible from external sources (Vercel's servers).

## Step 5: Deploy

1. Click **Deploy** in Vercel
2. Wait for the build to complete
3. Your app will be available at `https://your-project-name.vercel.app`

## Step 6: Verify Deployment

1. Check that your app loads correctly
2. Test the main functionality
3. Check the browser console for any errors
4. Verify API endpoints are working

## Troubleshooting

### Common Issues:

1. **Build Failures**: Check the build logs in Vercel dashboard
2. **Environment Variables**: Ensure all required variables are set
3. **Database Connection**: Verify Supabase is accessible from Vercel
4. **CORS Issues**: Check if your Supabase project allows requests from your Vercel domain

### Debugging:

- Check Vercel function logs in the dashboard
- Use browser developer tools to inspect network requests
- Verify environment variables are loaded correctly

## Post-Deployment

1. **Custom Domain**: Add a custom domain in Vercel settings if desired
2. **Monitoring**: Set up monitoring and analytics
3. **CI/CD**: Configure automatic deployments on Git pushes
4. **Backups**: Ensure your database has proper backup strategies

## Security Notes

- Never commit sensitive keys to your repository
- Use environment variables for all sensitive configuration
- Regularly rotate your Supabase keys
- Monitor your application for security issues

## Support

If you encounter issues:
1. Check Vercel's [documentation](https://vercel.com/docs)
2. Review the build logs in your Vercel dashboard
3. Check the [Next.js documentation](https://nextjs.org/docs)
4. Review Supabase's [deployment guide](https://supabase.com/docs/guides/deployment)
