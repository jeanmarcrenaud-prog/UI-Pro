// lib/circularBuffer.ts
// Role: Fixed-size circular buffer to prevent memory bloat from unlimited log/message accumulation

export class CircularBuffer<T> {
  private items: T[] = []
  private readonly maxSize: number

  constructor(maxSize: number = 100) {
    if (maxSize <= 0) {
      throw new Error('CircularBuffer maxSize must be positive')
    }
    this.maxSize = maxSize
  }

  /**
   * Add item to buffer, removing oldest if at capacity
   */
  push(item: T): void {
    if (this.items.length >= this.maxSize) {
      this.items.shift() // Remove oldest
    }
    this.items.push(item)
  }

  /**
   * Add multiple items efficiently
   */
  pushBatch(items: T[]): void {
    for (const item of items) {
      this.push(item)
    }
  }

  /**
   * Get all items
   */
  getAll(): T[] {
    return [...this.items]
  }

  /**
   * Get last n items
   */
  getLast(n: number): T[] {
    return this.items.slice(Math.max(0, this.items.length - n))
  }

  /**
   * Get first n items
   */
  getFirst(n: number): T[] {
    return this.items.slice(0, Math.min(n, this.items.length))
  }

  /**
   * Get size
   */
  get size(): number {
    return this.items.length
  }

  /**
   * Get capacity
   */
  get capacity(): number {
    return this.maxSize
  }

  /**
   * Get utilization percentage
   */
  get utilization(): number {
    return Math.round((this.size / this.maxSize) * 100)
  }

  /**
   * Check if empty
   */
  isEmpty(): boolean {
    return this.items.length === 0
  }

  /**
   * Check if full
   */
  isFull(): boolean {
    return this.items.length >= this.maxSize
  }

  /**
   * Clear all items
   */
  clear(): void {
    this.items = []
  }

  /**
   * Convert to array (for React rendering)
   */
  toArray(): T[] {
    return [...this.items]
  }
}
