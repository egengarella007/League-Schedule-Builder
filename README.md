# League Scheduler

A modern web application for production-quality league scheduling with optimization passes.

## Features

- **📥 Import**: Upload Excel files with time slots
- **🏆 Teams**: Manage divisions and teams with an intuitive interface
- **📅 Schedule**: Generate optimal schedules with visual feedback
- **🎨 Modern UI**: Clean, responsive design with dark theme
- **⚡ Fast**: Built with Next.js for optimal performance

## Tech Stack

- **Frontend**: Next.js 14, React 18, TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **File Processing**: XLSX library
- **Deployment**: Vercel

## Getting Started

### Local Development

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Run the development server**:
   ```bash
   npm run dev
   ```

3. **Open your browser**:
   Navigate to [http://localhost:3000](http://localhost:3000)

### Deployment on Vercel

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Deploy on Vercel**:
   - Connect your GitHub repository to Vercel
   - Vercel will automatically detect Next.js and deploy
   - Your app will be available at `https://your-app.vercel.app`

## File Format

Your Excel file should have the following structure:

| Event Start | Event End | Resource |
|-------------|-----------|----------|
| 9/6/25 9:00 PM | 9/6/25 10:20 PM | GPI - Rink 4 |
| 9/6/25 10:30 PM | 9/6/25 11:50 PM | GPI - Rink 1 |
| 9/7/25 8:00 PM | 9/7/25 9:20 PM | GPI - Rink 2 |

**Note**: Each row represents one available time slot. The scheduler will use all rows in the file.

## Usage

1. **Import Data**: Upload your Excel file with time slots
2. **Configure Teams**: Add divisions and teams
3. **Generate Schedule**: Create the optimal schedule for your league

## Development

### Project Structure

```
app/
├── components/          # React components
│   ├── ImportTab.tsx   # File upload and processing
│   ├── TeamsTab.tsx    # Division and team management
│   └── ScheduleTab.tsx # Schedule generation and display
├── globals.css         # Global styles
├── layout.tsx          # Root layout
└── page.tsx            # Main page with tabs
```

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details.
