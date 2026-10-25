import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'

const SOURCE_ROOT = resolve(process.cwd(), 'src')
const EXTENSIONS = ['.js', '.jsx', '.json', '.css']

function walk(directory) {
  return readdirSync(directory).flatMap((entry) => {
    const full = join(directory, entry)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}

function resolveSpecifier(fromFile, specifier) {
  const base = resolve(dirname(fromFile), specifier)
  const candidates = [base, ...EXTENSIONS.map((extension) => `${base}${extension}`), ...EXTENSIONS.map((extension) => join(base, `index${extension}`))]
  return candidates.find((candidate) => {
    try {
      return statSync(candidate).isFile()
    } catch {
      return false
    }
  })
}

const importPattern = /(?:from\s+|import\s*\()\s*['"](\.[^'"]+)['"]/g
const files = walk(SOURCE_ROOT).filter((file) => file.endsWith('.js') || file.endsWith('.jsx'))
const problems = []

for (const file of files) {
  const contents = readFileSync(file, 'utf8')
  for (const match of contents.matchAll(importPattern)) {
    const specifier = match[1]
    if (!resolveSpecifier(file, specifier)) {
      problems.push(`${file.replace(`${process.cwd()}/`, '')} -> ${specifier}`)
    }
  }
}

if (problems.length) {
  console.error(`Unresolved relative imports: ${problems.length}`)
  problems.forEach((problem) => console.error(`  ${problem}`))
  process.exit(1)
}

console.log(`All relative imports resolve (${files.length} modules checked).`)
