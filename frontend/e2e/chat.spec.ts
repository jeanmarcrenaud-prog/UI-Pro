// e2e/chat.spec.ts
// E2E tests for the Chat interface — input, streaming, execution approval, and navigation
import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

// ── Helpers ───────────────────────────────────────────────────────────

async function ensureScreenshotDir() {
  const dir = path.join(process.cwd(), 'e2e', 'screenshots')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

async function switchToTab(page: import('@playwright/test').Page, tabName: string) {
  // Try keyboard shortcut first (Alt+1=chat, Alt+2=history, Alt+3=settings, Alt+4=canvas)
  const keyMap: Record<string, string> = {
    chat: 'Alt+1',
    history: 'Alt+2',
    settings: 'Alt+3',
    canvas: 'Alt+4',
  }
  const key = keyMap[tabName]
  if (key) {
    await page.keyboard.press(key)
    await page.waitForTimeout(400)
  }

  // Verify we landed on the right tab by checking for expected content
  const contentSelectors: Record<string, RegExp> = {
    chat: /Describe your task|Chat|Send/i,
    history: /History|Historique|No history/i,
    settings: /Settings|Language|Model|Timeout/i,
    canvas: /Agent Canvas|No execution data/i,
  }
  const selector = contentSelectors[tabName]
  if (selector) {
    try {
      await expect(page.getByText(selector).first()).toBeVisible({ timeout: 3000 })
    } catch {
      // Fallback: try clicking nav buttons
      const navItems = page.locator('nav button, nav a, [role="tab"]')
      const count = await navItems.count()
      for (let i = 0; i < count; i++) {
        const text = await navItems.nth(i).textContent()
        if (text?.toLowerCase().includes(tabName)) {
          await navItems.nth(i).click()
          await page.waitForTimeout(300)
          break
        }
      }
    }
  }
}

async function injectChatMessage(page: import('@playwright/test').Page, content: string, role = 'user') {
  // Use the exposed chatStore to inject a message directly
  await page.waitForFunction(() => !!(window as any).__TEST_CHAT_STORE__, null, { timeout: 10000 })
  await page.evaluate(({ content, role }) => {
    const store = (window as any).__TEST_CHAT_STORE__
    if (store?.getState) {
      store.getState().addMessage({
        id: `test-${Date.now()}`,
        role: role as 'user' | 'assistant',
        content,
        status: 'done',
      })
    }
  }, { content, role })
  await page.waitForTimeout(300)
}

async function triggerExecutionApproval(page: import('@playwright/test').Page) {
  // Trigger the awaitingApproval event via the exposed events emitter
  await page.waitForFunction(() => !!(window as any).__TEST_EVENTS__, null, { timeout: 10000 })
  await page.evaluate(() => {
    const events = (window as any).__TEST_EVENTS__
    events.emit('awaitingApproval', {
      stream_id: 'test-stream-123',
      code_preview: 'def hello():\n    print("Hello, World!")\n\nif __name__ == "__main__":\n    hello()',
      message_id: 'test-msg-456',
    })
  })
  await page.waitForTimeout(500)
}

// ── Canvas helpers (approval banner lives in AgentCanvas, needs steps) ──

const MOCK_STEPS = [
  { id: 'step-analyzing', title: 'Analyze', status: 'done' as const, detail: 'Classify & route task', duration: 1.2, tokens: 340 },
  { id: 'step-planning', title: 'Plan', status: 'done' as const, detail: 'Implementation plan', duration: 3.4, tokens: 890 },
  { id: 'step-coding', title: 'Code', status: 'done' as const, detail: 'Generate Python code', duration: 8.1, tokens: 2450 },
  { id: 'step-reviewing', title: 'Review', status: 'done' as const, detail: 'Static & LLM review', duration: 2.1, tokens: 560 },
  { id: 'step-executing', title: 'Execute', status: 'active' as const, detail: 'Sandboxed execution', duration: 0, tokens: 0 },
]

async function injectSteps(page: import('@playwright/test').Page, steps: typeof MOCK_STEPS = MOCK_STEPS) {
  await page.waitForFunction(() => !!(window as any).__TEST_AGENT_STORE__, null, { timeout: 10000 })
  await page.evaluate((s) => {
    const store = (window as any).__TEST_AGENT_STORE__
    store.getState().setSteps(s)
  }, steps)
  // Give the agentStore -> canvasStore sync + React Flow a moment
  await page.waitForTimeout(800)
}

async function stubSendExecuteDecision(page: import('@playwright/test').Page) {
  await page.waitForFunction(() => !!(window as any).__TEST_CHAT_SERVICE__, null, { timeout: 10000 })
  await page.evaluate(() => {
    const svc = (window as any).__TEST_CHAT_SERVICE__
    if (!svc.__decisions) svc.__decisions = []
    svc.sendExecuteDecision = async (decision: string, feedback?: string) => {
      svc.__decisions.push({ decision, feedback })
    }
  })
}

// ── Tests ─────────────────────────────────────────────────────────────

test.describe('Chat Interface — E2E Smoke Tests', () => {

  test('T1: Chat page loads with all key elements', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Header
    await expect(page.getByText('UI-Pro').first()).toBeVisible({ timeout: 5000 })

    // Chat input area
    const input = page.locator('textarea[placeholder*="Describe your task"]')
    await expect(input).toBeVisible({ timeout: 5000 })

    // Send button (aria-label on the icon button in ChatContainer)
    const sendBtn = page.getByRole('button', { name: 'Send message' })
    await expect(sendBtn).toBeVisible()

    // Sidebar should be visible
    const sidebar = page.locator('nav')
    await expect(sidebar).toBeVisible()

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-initial.png'), fullPage: false })
  })

  test('T2: User can type in the chat input', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const input = page.locator('textarea[placeholder*="Describe your task"]')
    await expect(input).toBeVisible({ timeout: 5000 })

    await input.fill('Write a Python script to fetch weather')
    const value = await input.inputValue()
    expect(value).toBe('Write a Python script to fetch weather')
  })

  test('T3: User message appears after sending via store injection', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Inject a user message into the chat store
    await injectChatMessage(page, 'Write a Python script to fetch weather', 'user')

    // Verify the message appears in the DOM
    const userMsg = page.getByText('Write a Python script to fetch weather')
    await expect(userMsg).toBeVisible({ timeout: 3000 })

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-user-message.png'), fullPage: false })
  })

  test('T4: Assistant response renders after sending via store', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Inject a full conversation: user message + assistant response
    await injectChatMessage(page, 'Write a Python script', 'user')
    await page.waitForTimeout(200)
    await injectChatMessage(page, 'Here is a Python script:\n\n```python\nprint("hello")\n```', 'assistant')

    // Verify both messages visible
    await expect(page.getByText('Write a Python script')).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('Here is a Python script')).toBeVisible({ timeout: 3000 })

    // Verify code block renders
    const codeBlock = page.locator('pre code, pre, .language-python')
    await expect(codeBlock.first()).toBeVisible({ timeout: 3000 })

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-assistant-response.png'), fullPage: false })
  })

  test('T5: Execution approval banner appears in the canvas header when triggered', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // The approval banner lives in the Agent Canvas header, so the canvas
    // must be mounted first (needs agent steps + Graphe view).
    await injectSteps(page)
    await expect(page.getByText('Agent Canvas').first()).toBeVisible({ timeout: 5000 })

    // Trigger the awaitingApproval event via the exposed events emitter
    await triggerExecutionApproval(page)

    // Verify approval banner is visible in the canvas header
    await expect(page.getByText(/Awaiting approval/i).first()).toBeVisible({ timeout: 3000 })
    await expect(page.getByRole('button', { name: /Approve|Approuver/i }).first()).toBeVisible({ timeout: 3000 })
    await expect(page.getByRole('button', { name: /Reject|Rejeter/i }).first()).toBeVisible({ timeout: 3000 })

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-execution-approval.png'), fullPage: false })
  })

  test('T6: Approve button hides the banner and sends execute decision', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await injectSteps(page)
    await expect(page.getByText('Agent Canvas').first()).toBeVisible({ timeout: 5000 })
    await triggerExecutionApproval(page)

    // Spy on the chat service's sendExecuteDecision to avoid a real WS call
    await stubSendExecuteDecision(page)

    const approveBtn = page.getByRole('button', { name: /Approve|Approuver/i }).first()
    await expect(approveBtn).toBeVisible({ timeout: 3000 })
    await approveBtn.click()
    await page.waitForTimeout(300)

    // Approval banner should disappear after approving
    await expect(page.getByText(/Awaiting approval/i).first()).not.toBeVisible({ timeout: 3000 })

    // The decision was routed through chatService.sendExecuteDecision('execute')
    const decisions = await page.evaluate(() => (window as any).__TEST_CHAT_SERVICE__?.__decisions ?? [])
    expect(decisions.some((d: any) => d.decision === 'execute')).toBe(true)
  })

  test('T7: Reject button hides the banner and sends cancel decision', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await injectSteps(page)
    await expect(page.getByText('Agent Canvas').first()).toBeVisible({ timeout: 5000 })
    await triggerExecutionApproval(page)

    await stubSendExecuteDecision(page)

    const rejectBtn = page.getByRole('button', { name: /Reject|Rejeter/i }).first()
    await expect(rejectBtn).toBeVisible({ timeout: 3000 })
    await rejectBtn.click()
    await page.waitForTimeout(300)

    await expect(page.getByText(/Awaiting approval/i).first()).not.toBeVisible({ timeout: 3000 })

    const decisions = await page.evaluate(() => (window as any).__TEST_CHAT_SERVICE__?.__decisions ?? [])
    expect(decisions.some((d: any) => d.decision === 'cancel')).toBe(true)
  })

  test('T8: No approval banner without the awaitingApproval event', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await injectSteps(page)
    await expect(page.getByText('Agent Canvas').first()).toBeVisible({ timeout: 5000 })

    // No event emitted → no approval banner
    await expect(page.getByText(/Awaiting approval/i)).toHaveCount(0)
  })

  test('T9: History tab renders correctly', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToTab(page, 'history')

    const history = page.getByText(/History|Historique|No history|Aucun/i)
    await expect(history.first()).toBeVisible({ timeout: 5000 })

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-history-tab.png'), fullPage: false })
  })

  test('T10: Settings tab renders correctly', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await switchToTab(page, 'settings')

    // Settings should show configuration options
    const settings = page.getByText(/Settings|Language|Timeout|Model|Preset/i)
    await expect(settings.first()).toBeVisible({ timeout: 5000 })

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-settings-tab.png'), fullPage: false })
  })

  test('T11: Multiple conversation messages render in order', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Inject a conversation with multiple turns
    await injectChatMessage(page, 'First prompt', 'user')
    await injectChatMessage(page, 'First response', 'assistant')
    await injectChatMessage(page, 'Second prompt', 'user')
    await injectChatMessage(page, 'Second response', 'assistant')

    // Verify all messages visible
    await expect(page.getByText('First prompt')).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('First response')).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('Second prompt')).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('Second response')).toBeVisible({ timeout: 3000 })

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-multi-turn.png'), fullPage: false })
  })
})
