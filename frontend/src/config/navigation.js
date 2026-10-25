import { Activity, Database, Gauge, Table2 } from 'lucide-react'

export const NAV_ITEMS = [
  {
    path: '/',
    label: 'Overview',
    index: '01',
    eyebrow: 'Trading workspace',
    title: 'Decision-point forecast overview',
    description:
      'The national wind generation forecast as it stood at the configured decision cutoff, set against realised wind generation for the selected delivery period.',
    icon: Gauge
  },
  {
    path: '/explorer',
    label: 'Forecast Explorer',
    index: '02',
    eyebrow: 'Record inspector',
    title: 'Half-hourly forecast explorer',
    description:
      'Every delivery period in the selection, with the publication actually available at the cutoff, the realised actual and the resulting signed error.',
    icon: Table2
  },
  {
    path: '/accuracy',
    label: 'Accuracy Lab',
    index: '03',
    eyebrow: 'Evaluation',
    title: 'Forecast accuracy evaluation',
    description:
      'Error diagnostics and cutoff comparison for the selected records. Every figure below is recalculated from the matched observations.',
    icon: Activity
  },
  {
    path: '/provenance',
    label: 'Data Provenance',
    index: '04',
    eyebrow: 'Transparency',
    title: 'Data provenance and quality',
    description:
      'Where every number comes from: retrieval timestamps, record counts, duplicate handling, cache state and the limitations of the underlying datasets.',
    icon: Database
  }
]

export function findNavItem(pathname) {
  return NAV_ITEMS.find((item) => item.path === pathname) || NAV_ITEMS[0]
}
