import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './components/ui/ToastProvider'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { AnalysisParamsProvider } from './hooks/useAnalysisParams'
import { DatasetProvider } from './hooks/useDataset'
import { AppLayout } from './components/layout/AppLayout'
import { OverviewPage } from './pages/OverviewPage'
import { ForecastExplorerPage } from './pages/ForecastExplorerPage'
import { AccuracyLabPage } from './pages/AccuracyLabPage'
import { DataProvenancePage } from './pages/DataProvenancePage'
import { NotFoundPage } from './pages/NotFoundPage'

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AnalysisParamsProvider>
          <DatasetProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<AppLayout />}>
                  <Route index element={<OverviewPage />} />
                  <Route path="explorer" element={<ForecastExplorerPage />} />
                  <Route path="accuracy" element={<AccuracyLabPage />} />
                  <Route path="provenance" element={<DataProvenancePage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </DatasetProvider>
        </AnalysisParamsProvider>
      </ToastProvider>
    </ErrorBoundary>
  )
}
