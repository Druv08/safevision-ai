import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { EmptyState } from './components/States'
import { Activity } from './pages/Activity'
import { AppShell } from './pages/AppShell'
import { Data } from './pages/Data'
import { Intelligence } from './pages/Intelligence'
import { Landing } from './pages/Landing'
import { Overview } from './pages/Overview'
import { Settings } from './pages/Settings'
import { Workspace } from './pages/Workspace'
import { StoreProvider } from './store'
import './styles.css'

const notFound = (
  <div className="page"><div className="card"><EmptyState icon="search" title="Nothing here" body="That view doesn't exist (yet)." action={<Link to="/app" className="btn">Back to overview</Link>} /></div></div>
)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <StoreProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<AppShell />}>
            <Route index element={<Overview />} />
            <Route path="workspace" element={<Workspace />} />
            <Route path="intelligence" element={<Intelligence />} />
            <Route path="activity" element={<Activity />} />
            <Route path="data" element={<Data />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={notFound} />
          </Route>
          <Route path="*" element={<AppShell />}>
            <Route path="*" element={notFound} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  </StrictMode>,
)
