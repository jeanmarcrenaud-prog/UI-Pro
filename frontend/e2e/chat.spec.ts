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

    // Send button
    const sendBtn = page.locator('button').filter({ hasText: '➤' })
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

  test('T5: Execution approval buttons appear when triggered', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Inject a conversation first
    await injectChatMessage(page, 'Generate a Python script', 'user')
    await injectChatMessage(page, 'Generated code:\n\n```python\ndef hello():\n    pass\n```', 'assistant')

    // Trigger the execution approval event
    await triggerExecutionApproval(page)

    // Verify approval UI is visible
    // 1. Title
    await expect(page.getByText(/Code ready.*execute or adjust/i)).toBeVisible({ timeout: 3000 })
    // 2. Awaiting approval badge
    await expect(page.getByText(/Awaiting approval/i)).toBeVisible({ timeout: 3000 })
    // 3. Action buttons
    await expect(page.getByText('Execute').first()).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('Correct').first()).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('Cancel').first()).toBeVisible({ timeout: 3000 })
    // 4. Code preview
    await expect(page.getByText(/def hello/)).toBeVisible({ timeout: 3000 })

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-execution-approval.png'), fullPage: false })
  })

  test('T6: Correct button reveals feedback textarea', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await injectChatMessage(page, 'Generate code', 'user')
    await injectChatMessage(page, '```python\nprint("ok")\n```', 'assistant')
    await triggerExecutionApproval(page)

    // Click "Correct"
    await page.getByText('Correct').first().click()
    await page.waitForTimeout(300)

    // Verify feedback textarea appears
    const feedbackInput = page.locator('textarea[placeholder*="Describe what to change"]')
    await expect(feedbackInput).toBeVisible({ timeout: 3000 })

    // Button text should change to "Send correction"
    await expect(page.getByText('Send correction').first()).toBeVisible({ timeout: 3000 })

    // Type feedback
    await feedbackInput.fill('Use async/await pattern')
    const value = await feedbackInput.inputValue()
    expect(value).toBe('Use async/await pattern')

    const dir = await ensureScreenshotDir()
    await page.screenshot({ path: path.join(dir, 'chat-correction-feedback.png'), fullPage: false })
  })

  test('T7: Execute button click sends decision via chatService', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await injectChatMessage(page, 'Generate code', 'user')
    await injectChatMessage(page, '```python\nprint("ok")\n```', 'assistant')
    await triggerExecutionApproval(page)

    // Spy on the chat service's sendExecuteDecision method if available
    // At minimum, verify the button click doesn't throw and approval UI dismisses
    const executeBtn = page.getByText('Execute').first()
    await expect(executeBtn).toBeVisible({ timeout: 3000 })

    // Click execute
    await executeBtn.click()
    await page.waitForTimeout(500)

    // Approval panel should disappear after clicking execute
    await expect(page.getByText(/Code ready.*execute or adjust/i)).not.toBeVisible({ timeout: 3000 })
  })

  test('T8: Cancel button dismisses approval panel', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await injectChatMessage(page, 'Generate code', 'user')
    await injectChatMessage(page, '```python\nprint("ok")\n```', 'assistant')
    await triggerExecutionApproval(page)

    const cancelBtn = page.getByText('Cancel').first()
    await expect(cancelBtn).toBeVisible({ timeout: 3000 })

    await cancelBtn.click()
    await page.waitForTimeout(500)

    await expect(page.getByText(/Code ready.*execute or adjust/i)).not.toBeVisible({ timeout: 3000 })
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
