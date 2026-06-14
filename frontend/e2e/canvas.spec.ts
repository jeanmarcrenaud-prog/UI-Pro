// e2e/canvas.spec.ts
// Visual tests for the Agent Canvas (React Flow graph)
import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

// ── Mock data ─────────────────────────────────────────────────────────

const MOCK_STEPS = [
  { id: 'step-analyzing', title: 'Analyze', status: 'done' as const, detail: 'Classify & route task', duration: 1.2, tokens: 340 },
  { id: 'step-planning', title: 'Plan', status: 'done' as const, detail: 'Implementation plan', duration: 3.4, tokens: 890 },
  { id: 'step-coding', title: 'Code', status: 'done' as const, detail: 'Generate Python code', duration: 8.1, tokens: 2450 },
  { id: 'step-reviewing', title: 'Review', status: 'done' as const, detail: 'Static & LLM review', duration: 2.1, tokens: 560 },
  { id: 'step-executing', title: 'Execute', status: 'active' as const, detail: 'Sandboxed execution', duration: 0, tokens: 0 },
]

// ── Helpers ───────────────────────────────────────────────────────────

async function switchToCanvas(page: import('@playwright/test').Page) {
  await page.keyboard.press('Alt+4')
  await page.waitForTimeout(600)
  const onCanvas = await page.getByText(/Agent Canvas|No execution data/i).isVisible().catch(() => false)
  if (onCanvas) return
  const navItems = page.locator('nav button, nav a').filter({ hasNot: page.locator('[hidden]') })
  const count = await navItems.count()
  for (let i = 0; i < count; i++) {
    const text = await navItems.nth(i).textContent()
    if (text?.toLowerCase().includes('canvas') || text?.includes('🔀')) {
      await navItems.nth(i).click()
      await page.waitForTimeout(300)
      return
    }
  }
}

async function injectSteps(page: import('@playwright/test').Page) {
  // Wait until the store is exposed on window (dynamic import may be async)
  await page.waitForFunction(() => !!(window as any).__TEST_AGENT_STORE__, null, { timeout: 10000 })
  await page.evaluate((steps) => {
    const store = (window as any).__TEST_AGENT_STORE__
    store.getState().setSteps(steps)
  }, MOCK_STEPS)
  await page.waitForTimeout(500)
}

async function ensureScreenshotDir() {
  const dir = path.join(process.cwd(), 'e2e', 'screenshots')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

// ── Tests ─────────────────────────────────────────────────────────────

test.describe('Agent Canvas — Visual & Smoke Tests', () => {

  test('T1: sidebar has Canvas tab with keyboard shortcut Alt+4', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const canvasTab = page.locator('nav button, nav a').filter({ hasText: /canvas|🔀/i })
    await expect(canvasTab.first()).toBeVisible({ timeout: 5000 })

    await switchToCanvas(page)

    const canvasContent = page.getByText(/Agent Canvas|No execution data|Export as/i)
    await expect(canvasContent.first()).toBeVisible({ timeout: 3000 })
  })

  test('T2: empty state renders correctly', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToCanvas(page)

    await expect(page.getByText(/No execution data/i)).toBeVisible({ timeout: 3000 })
    await expect(page.getByTitle('Export as PNG')).toBeVisible()
    await expect(page.getByTitle('Export as JSON')).toBeVisible()

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'canvas-empty.png'), fullPage: false })
  })

  test('T3: React Flow graph renders with mock pipeline data', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToCanvas(page)

    await injectSteps(page)
    await page.waitForTimeout(800)

    const reactFlow = page.locator('.react-flow')
    await expect(reactFlow).toBeVisible({ timeout: 5000 })

    const nodeCount = await page.locator('.react-flow__node').count()
    expect(nodeCount).toBeGreaterThanOrEqual(1)

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'canvas-with-data.png'), fullPage: false })
  })

  test('T4: timeline sidebar visible in standalone mode', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToCanvas(page)
    await injectSteps(page)
    await page.waitForTimeout(500)

    const visibleCount = await page.locator('text=/Analyze|Plan|Code|Review|Execute/i').count()
    expect(visibleCount).toBeGreaterThanOrEqual(3)
  })

  test('T5: timeline step click selects node', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToCanvas(page)
    await injectSteps(page)
    await page.waitForTimeout(500)

    const analyzeBtn = page.getByText('Analyze').first()
    await analyzeBtn.click()
    await page.waitForTimeout(400)

    const detailPanel = page.locator('[class*="NodeDetail"], [class*="detail-panel"]').first()
    const detailVisible = await detailPanel.isVisible().catch(() => false)

    if (detailVisible) {
      await expect(detailPanel).toBeVisible()
      const dir = await ensureScreenshotDir()
      await page.screenshot({ path: path.join(dir, 'canvas-node-detail.png'), fullPage: false })
    } else {
      const selectedNode = page.locator('.react-flow__node.selected').first()
      const selected = await selectedNode.isVisible().catch(() => false)
      expect(selected || detailVisible).toBeTruthy()
    }
  })

  test('T6: export buttons are functional', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToCanvas(page)
    await injectSteps(page)
    await page.waitForTimeout(500)

    const pngBtn = page.getByTitle('Export as PNG')
    await expect(pngBtn).toBeEnabled()
    await pngBtn.click()
    await page.waitForTimeout(300)

    const jsonBtn = page.getByTitle('Export as JSON')
    await expect(jsonBtn).toBeEnabled()
    await jsonBtn.click()
    await page.waitForTimeout(300)
  })

  test('T7: page header visible on canvas tab', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToCanvas(page)

    await expect(page.getByText(/Agent Canvas/i).first()).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('UI-Pro').first()).toBeVisible()
  })
})
