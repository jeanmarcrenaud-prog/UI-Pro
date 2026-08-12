// e2e/canvas.spec.ts
// Visual & smoke tests for the Agent Canvas (React Flow graph).
//
// Architecture note (current):
//   - The canvas lives INSIDE ChatContainer (above the messages), NOT in a
//     sidebar tab. It renders when the agent store has steps and the
//     "Graphe" view is active (canvasView defaults to true).
//   - Tests inject mock steps through window.__TEST_AGENT_STORE__
//     (exposed by app/page.tsx in dev), which the agentCanvasStore
//     auto-syncs into the canvas graph.
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

async function gotoApp(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
}

async function injectSteps(page: import('@playwright/test').Page, steps: typeof MOCK_STEPS = MOCK_STEPS) {
  // Wait until the agent store is exposed on window (dynamic import may be async)
  await page.waitForFunction(() => !!(window as any).__TEST_AGENT_STORE__, null, { timeout: 10000 })
  await page.evaluate((s) => {
    const store = (window as any).__TEST_AGENT_STORE__
    store.getState().setSteps(s)
  }, steps)
  // Give the agentStore -> canvasStore sync + React Flow a moment
  await page.waitForTimeout(800)
}

async function ensureScreenshotDir() {
  const dir = path.join(process.cwd(), 'e2e', 'screenshots')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

// ── Tests ─────────────────────────────────────────────────────────────

test.describe('Agent Canvas — Visual & Smoke Tests (in ChatContainer)', () => {

  test('T1: canvas is hidden until agent steps exist', async ({ page }) => {
    await gotoApp(page)

    // No steps => no Agent Canvas block, no React Flow
    await expect(page.locator('.agent-canvas')).toHaveCount(0)
    await expect(page.locator('.react-flow')).toHaveCount(0)
    await expect(page.getByText(/Step Progress|Agent Canvas/).first()).not.toBeVisible()
  })

  test('T2: canvas appears above messages after steps are injected', async ({ page }) => {
    await gotoApp(page)
    await injectSteps(page)

    // Header + graph + controls visible
    await expect(page.getByText('Agent Canvas').first()).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.react-flow')).toBeVisible({ timeout: 5000 })
    await expect(page.getByTitle('Export as PNG')).toBeVisible()
    await expect(page.getByTitle('Export as JSON')).toBeVisible()

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'canvas-with-data.png'), fullPage: false })
  })

  test('T3: React Flow graph renders pipeline nodes from mock steps', async ({ page }) => {
    await gotoApp(page)
    await injectSteps(page)

    const reactFlow = page.locator('.react-flow')
    await expect(reactFlow).toBeVisible({ timeout: 5000 })

    // 5 injected steps -> at least 5 nodes in the graph
    const nodeCount = await page.locator('.react-flow__node').count()
    expect(nodeCount).toBeGreaterThanOrEqual(5)
  })

  test('T4: timeline sidebar is visible with step titles', async ({ page }) => {
    await gotoApp(page)
    await injectSteps(page)

    await expect(page.getByText('Timeline').first()).toBeVisible({ timeout: 5000 })

    for (const step of MOCK_STEPS) {
      await expect(page.getByText(step.title).first()).toBeVisible({ timeout: 3000 })
    }
  })

  test('T5: clicking a timeline step opens the node detail panel', async ({ page }) => {
    await gotoApp(page)
    await injectSteps(page)

    // Click "Analyze" inside the timeline sidebar (w-56), not the graph node
    const timeline = page.locator('div.w-56')
    await expect(timeline).toBeVisible({ timeout: 5000 })
    await timeline.getByText('Analyze').click()
    await page.waitForTimeout(400)

    // Either the detail panel (close button) or a selected React Flow node
    const closeBtn = page.locator('[aria-label="Close detail panel"]')
    const closeVisible = await closeBtn.isVisible().catch(() => false)
    if (closeVisible) {
      await expect(closeBtn).toBeVisible()
      await expect(page.getByText(/Analyze|Classify & route task/).first()).toBeVisible()
      const dir = await ensureScreenshotDir()
      await page.screenshot({ path: path.join(dir, 'canvas-node-detail.png'), fullPage: false })
    } else {
      const selectedNode = page.locator('.react-flow__node.selected')
      await expect(selectedNode.first()).toBeVisible({ timeout: 3000 })
    }
  })

  test('T6: export buttons are functional', async ({ page }) => {
    await gotoApp(page)
    await injectSteps(page)

    const pngBtn = page.getByTitle('Export as PNG')
    await expect(pngBtn).toBeEnabled()
    await pngBtn.click()
    await page.waitForTimeout(300)

    const jsonBtn = page.getByTitle('Export as JSON')
    await expect(jsonBtn).toBeEnabled()
    await jsonBtn.click()
    await page.waitForTimeout(300)
  })

  test('T7: Liste/Graphe toggle switches between Step Progress and canvas', async ({ page }) => {
    await gotoApp(page)
    await injectSteps(page)

    // Default: graph view
    await expect(page.getByText('Agent Canvas').first()).toBeVisible({ timeout: 5000 })

    // Switch to list view
    await page.getByRole('button', { name: /Liste/i }).click()
    await expect(page.getByText('Step Progress').first()).toBeVisible({ timeout: 3000 })
    await expect(page.locator('.agent-canvas')).toHaveCount(0)

    // Switch back to graph view
    await page.getByRole('button', { name: /Graphe/i }).click()
    await expect(page.locator('.react-flow')).toBeVisible({ timeout: 5000 })
  })

  test('T8: page header remains visible with the canvas', async ({ page }) => {
    await gotoApp(page)
    await injectSteps(page)

    await expect(page.getByText('UI-Pro').first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('Agent Canvas').first()).toBeVisible()
  })
})
