# ACOG Dashboard

Frontend dashboard for the Automated Content Orchestration & Generation (ACOG) system. Built with Next.js 14, TypeScript, and TailwindCSS.

## Quick Start

### Prerequisites

- Node.js 18+
- npm or yarn
- ACOG Backend running at http://localhost:8000

### Installation

```bash
cd apps/dashboard
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Configuration

Create a `.env.local` file (copy from `.env.example`):

```env
NEXT_PUBLIC_ACOG_API_URL=http://localhost:8000/api/v1
```

## Project Structure

```
apps/dashboard/
├── app/                    # Next.js App Router pages
│   ├── channels/           # Channel list and detail pages
│   ├── episodes/           # Episode detail page
│   ├── layout.tsx          # Root layout with sidebar
│   └── page.tsx            # Root redirect to /channels
│
├── components/
│   ├── assets/             # Asset list and viewer components
│   ├── channels/           # Channel-specific components
│   ├── episodes/           # Episode-specific components
│   ├── layout/             # Sidebar and Header components
│   └── ui/                 # Reusable UI components
│
├── hooks/                  # SWR data fetching hooks
│   ├── useChannels.ts
│   ├── useChannel.ts
│   ├── useEpisode.ts
│   ├── usePipelineStatus.ts
│   └── useAssets.ts
│
└── lib/
    ├── api.ts              # API client with typed endpoints
    ├── types.ts            # TypeScript type definitions
    └── utils.ts            # Helper utilities
```

## Features

### Channel Management
- View all channels with status and episode counts
- Create new channels with persona configuration
- View channel details and associated episodes

### Episode Management
- Create episodes with title, idea brief, and priority
- View episode details including plan, script, and metadata
- Pipeline visualization with stage status indicators

### Pipeline Controls
- Run Stage 1 pipeline (planning, scripting, metadata)
- Real-time status updates with automatic polling
- Error display and retry capabilities

### Asset Viewing
- List all assets for an episode
- View plan, script, and metadata content in modal
- Asset type indicators with color coding

## API Integration

The dashboard connects to the FastAPI backend via the API client in `lib/api.ts`. All endpoints are typed and return standardized `ApiResponse<T>` objects.

### Key Endpoints Used

- `GET /channels` - List channels
- `POST /channels` - Create channel
- `GET /channels/{id}` - Channel details
- `GET /channels/{id}/episodes` - Channel episodes
- `POST /episodes` - Create episode
- `GET /episodes/{id}` - Episode details
- `GET /assets/episode/{id}` - Episode assets
- `POST /pipeline/episodes/{id}/run-stage-1` - Run Stage 1
- `GET /pipeline/episodes/{id}/status` - Pipeline status

## Tech Stack

- **Next.js 14** - App Router with Server/Client Components
- **TypeScript** - Strict mode enabled
- **TailwindCSS** - Utility-first styling
- **SWR** - Data fetching with caching and revalidation

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Check TypeScript types
